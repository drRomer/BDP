"""Bake bridge props (Tripo GLB) into billboard sprites + cut out 2D props from images.
Outputs out/props/<key>.png and props.json {key:{w,h,axf,ayf,[hxf,hyf]}}"""
import asyncio, sys, json, math, os
sys.path.insert(0, '/home/claude/brigada')
from bk import Baker, img_of
from PIL import Image, ImageOps, ImageFilter, ImageDraw
import numpy as np

OUT = '/home/claude/brigada/out/props'; os.makedirs(OUT, exist_ok=True)
PITCH = math.degrees(math.atan2(12, 18))
# key, glb, rotY (deg, makes the model face +Z), extra yaw, size target (dim, value), mirror copies
GLB = [
    ('sedanA', 'p_22361556', 0, 24, ('len', 2.9)),
    ('sedanB', 'p_22361556', 0, -28, ('len', 2.9)),
    ('pickupA', 'p_97a03782', 90, -22, ('len', 3.1)),
    ('pickupB', 'p_97a03782', 90, 30, ('len', 3.1)),
    ('truck', 'p_ecf79461', 0, 14, ('len', 5.0)),
    ('barrierA', 'p_7c62a8ba', 0, 12, ('len', 2.1)),
    ('barrierB', 'p_7c62a8ba', 0, -18, ('len', 2.1)),
    ('lampR', 'p_82598741', 0, 0, ('hgt', 6.6)),
    ('barricadeA', 'p_4063448d', 0, 14, ('len', 2.0)),
    ('barricadeB', 'p_4063448d', 0, -20, ('len', 2.0)),
    ('cone', 'p_1f508cef', 0, 20, ('hgt', 0.78)),
    ('bags', 'p_fe95d69b', 180, 10, ('len', 2.3)),
    ('barrel', 'p_52a57aca', 0, 30, ('hgt', 1.0)),
    ('warn', 'p_77f91fa3', 180, 8, ('hgt', 2.5)),
    ('gantry', 'p_73f675eb', 180, 0, ('len', 13.0)),
    ('chevron', 'p_0bd949bc', 180, 12, ('hgt', 1.9)),
    ('crateW', 'p_7bfc2b8f', 0, 0, ('len', 1.9)),
    ('crateM', 'p_bbb90883', 0, 0, ('len', 1.35)),
    ('gateF', 'p_ae668058', 180, 0, ('hgt', 2.9)),
    ('tower', 'p_5f4c5ac9', 0, 8, ('hgt', 26.0)),
    ('plat', 'obj:t_af320455', 0, 0, ('len', 12.0)),
]
TARGET_PX = 300
BIG = {'gantry': 640, 'truck': 360, 'tower': 520, 'gateF': 360, 'plat': 520}  # max sprite dimension


async def bake_glb(b, key, glb, rot, yaw, size):
    if glb.startswith('obj:'):
        d = glb[4:]; obj = [f for f in os.listdir('/home/claude/brigada/in/' + d) if f.endswith('.obj')][0]
        T = {k: next(('/in/%s/%s' % (d, f) for f in os.listdir('/home/claude/brigada/in/' + d) if f.endswith(suf)), None)
             for k, suf in (('map', 'basecolor.jpg'), ('normal', 'normal.jpg'), ('rough', 'roughness.jpg'), ('metal', 'metallic.jpg'))}
        bb = await b.js('([u,t])=>B.loadOBJ(u,t)', ['/in/%s/%s' % (d, obj), T])
    else:
        bb = await b.js('(u)=>B.loadGLB(u)', '/in/glb/%s.glb' % glb)
    mn, mx = bb['min'], bb['max']
    dims = [mx[i] - mn[i] for i in range(3)]
    if size[0] == 'len': sc = size[1] / max(dims[0], dims[2])
    else: sc = size[1] / dims[1]
    # center on x/z, base on y=0, then rotate
    cx, cz = (mn[0] + mx[0]) / 2, (mn[2] + mx[2]) / 2
    r = math.radians(rot + yaw); c, s = math.cos(r), math.sin(r)
    # position so that the rotated & scaled model's base center sits at the origin
    px = -(cx * c + cz * s) * sc; pz = -(-cx * s + cz * c) * sc
    await b.js('([p,r,s])=>B.setRootTransform(p,r,s)', [[px, -mn[1] * sc, pz], rot + yaw, sc])
    await b.js('(y)=>B.view(y,%f)' % ({'gantry': 12.0, 'gateF': 18.0, 'tower': 14.0}.get(key, PITCH)), 180)
    x0, x1, y0, y1 = await b.js('()=>B.bounds(29,false)')
    ext = max(x1 - x0, y1 - y0) * 1.25
    ppu = BIG.get(key, TARGET_PX) / max(x1 - x0, y1 - y0)
    pad = 0.12 * ext
    L = x0 - pad; R = x1 + pad * 1.6; T = y1 + pad * .5; Bt = min(y0, 0) - pad
    W = int(math.ceil((R - L) * ppu)); H = int(math.ceil((T - Bt) * ppu))
    d = await b.js('([l,r,t,bt,w,h,s])=>B.frame(l,r,t,bt,w,h,s)', [L, R, T, Bt, W, H, key not in ('gantry', 'gateF', 'tower', 'crateW', 'crateM')])
    im = img_of(d)
    ox = -L * ppu; oy = T * ppu
    meta = {}
    if key.startswith('lamp'):
        # lamp head: highest-farthest vertex region -> approximate with bounds top and arm side
        meta['head'] = None
    bx = im.getbbox(); im = im.crop(bx)
    ox -= bx[0]; oy -= bx[1]
    w_units = im.width / ppu; h_units = im.height / ppu
    return im, {'w': round(w_units, 3), 'h': round(h_units, 3), 'axf': round(ox / im.width, 4), 'ayf': round(oy / im.height, 4)}


def cutout(path, key, target_h, bg_tol=38):
    im = Image.open(path).convert('RGB'); a = np.array(im).astype(np.int32)
    Hh, Ww = a.shape[:2]
    border = np.concatenate([a[0], a[-1], a[:, 0], a[:, -1]])
    ref = np.median(border, axis=0)
    dist = np.sqrt(((a - ref) ** 2).sum(-1))
    bgc = dist < bg_tol
    # flood fill from the borders through background-like pixels
    from collections import deque
    seen = np.zeros((Hh, Ww), bool); q = deque()
    for x in range(Ww):
        for y in (0, Hh - 1):
            if bgc[y, x] and not seen[y, x]: seen[y, x] = True; q.append((y, x))
    for y in range(Hh):
        for x in (0, Ww - 1):
            if bgc[y, x] and not seen[y, x]: seen[y, x] = True; q.append((y, x))
    while q:
        y, x = q.popleft()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < Hh and 0 <= nx < Ww and not seen[ny, nx] and bgc[ny, nx]:
                seen[ny, nx] = True; q.append((ny, nx))
    alpha = np.where(seen, 0, 255).astype(np.uint8)
    am = Image.fromarray(alpha).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(1.2))
    rgba = im.convert('RGBA'); rgba.putalpha(am)
    bx = rgba.getbbox(); rgba = rgba.crop(bx)
    sc = 260 / rgba.height
    rgba = rgba.resize((max(1, int(rgba.width * sc)), 260), Image.LANCZOS)
    # add a soft contact shadow under the object
    sh_h = int(rgba.height * 0.12); can = Image.new('RGBA', (int(rgba.width * 1.25), rgba.height + sh_h // 2), (0, 0, 0, 0))
    sh = Image.new('RGBA', can.size, (0, 0, 0, 0)); d = ImageDraw.Draw(sh)
    cxp = can.width / 2; base = rgba.height - 4
    d.ellipse((cxp - rgba.width * 0.55, base - sh_h * .45, cxp + rgba.width * 0.62, base + sh_h * .45), fill=(0, 0, 0, 105))
    sh = sh.filter(ImageFilter.GaussianBlur(6))
    can.alpha_composite(sh); can.alpha_composite(rgba, (int((can.width - rgba.width) / 2), 0))
    h_units = target_h * can.height / rgba.height
    w_units = h_units * can.width / can.height
    return can, {'w': round(w_units, 3), 'h': round(h_units, 3), 'axf': 0.5, 'ayf': round(base / can.height, 4)}


async def main():
    meta = json.load(open(os.path.join(OUT, 'props.json'))) if len(sys.argv) > 1 else {}
    only = set(sys.argv[1:])
    async with Baker() as b:
        for key, glb, rot, yaw, size in GLB:
            if only and key not in only: continue
            im, m = await bake_glb(b, key, glb, rot, yaw, size)
            im.save(os.path.join(OUT, key + '.png')); meta[key] = m
            print(key, im.size, m)
            if key == 'lampR':
                mi = ImageOps.mirror(im); mi.save(os.path.join(OUT, 'lampL.png'))
                ml = dict(m); ml['axf'] = round(1 - m['axf'], 4); meta['lampL'] = ml
                # head = topmost opaque pixel row region, horizontal extreme on the arm side
                a = np.array(im)[..., 3]; ys, xs = np.nonzero(a > 40)
                top = ys.min(); band = xs[ys < top + max(4, int(im.height * 0.03))]
                hx = band.mean() / im.width
                meta['lampR'].update({'hxf': round(hx, 4), 'hyf': round((top + im.height * 0.015) / im.height, 4)})
                meta['lampL'].update({'hxf': round(1 - hx, 4), 'hyf': meta['lampR']['hyf']})
    if not only or 'gantry' in only:
        meta['gantry']['panels'] = [[0.175, 0.045, 0.53, 0.295], [0.553, 0.045, 0.815, 0.295]]
    # warning sign: paint an exclamation mark in the blank white triangle
    from PIL import ImageFont
    im = Image.open(os.path.join(OUT, 'warn.png')).convert('RGBA'); a = np.array(im).astype(int)
    wmask = (a[..., 0] > 165) & (a[..., 1] > 160) & (a[..., 2] > 145) & (a[..., 3] > 220)
    red = (a[..., 0] > 140) & (a[..., 1] < 95) & (a[..., 2] < 95) & (a[..., 3] > 200)
    ys, xs = np.nonzero(red)
    if len(xs) and (not only or 'warn' in only):
        top, bot = np.percentile(ys, 1), np.percentile(ys, 99); l, r = np.percentile(xs, 1), np.percentile(xs, 99)
        hgt = bot - top; cx = (l + r) / 2
        f = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', max(10, int(hgt * 0.5)))
        d = ImageDraw.Draw(im); d.text((cx, top + hgt * 0.6), '!', font=f, fill=(24, 22, 22, 255), anchor='mm')
        im.save(os.path.join(OUT, 'warn.png'))
    if not only or 'gateF' in only:
        im = Image.open(os.path.join(OUT, 'gateF.png')).convert('RGBA'); a = np.array(im).astype(np.float32)
        al = a[..., 3] > 128; Hh = a.shape[0]
        cov = al[int(Hh * .45):].mean(0)          # column coverage in the lower half -> pillars
        cols = np.nonzero(cov > .5)[0]; mid = a.shape[1] / 2
        lcols = cols[cols < mid]; rcols = cols[cols > mid]
        pl = (lcols.max() + 2) / a.shape[1]; pr = (rcols.min() - 2) / a.shape[1]
        rows = np.nonzero(al[:, int(a.shape[1] * .5)])[0]; bh = (rows.max() + 2) / Hh if len(rows) else .2
        meta['gateF'].update({'pl': round(float(pl), 4), 'pr': round(float(pr), 4), 'bh': round(float(bh), 4)})
        lum = a[..., :3].mean(-1); sat = a[..., :3].max(-1) - a[..., :3].min(-1)
        strip = (lum > 185) & (sat < 40) & al
        for tag, col in (('gateA', (60, 150, 255)), ('gateM', (70, 215, 255)), ('gateB', (255, 60, 70))):
            o = a.copy(); k = (lum[strip] / 255.0)[:, None]
            o[strip, :3] = np.clip(np.array(col)[None, :] * (0.55 + 0.7 * k), 0, 255)
            Image.fromarray(o.astype(np.uint8)).save(os.path.join(OUT, tag + '.png')); meta[tag] = dict(meta['gateF'])
        print('gate slices', meta['gateF'], 'strip px', int(strip.sum()))
    json.dump(meta, open(os.path.join(OUT, 'props.json'), 'w'), indent=1)

asyncio.run(main())
