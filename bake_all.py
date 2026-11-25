"""Bake every character animation into sprite sheets + metadata for Brigada del Puente.
usage: bake_all.py [char ...]   (default: all)
Outputs /home/claude/brigada/out/sheets/<key>.png and <key>.json
"""
import asyncio, sys, json, math, os
sys.path.insert(0, '/home/claude/brigada')
from bk import Baker, tex_for, img_of
from PIL import Image, ImageOps

OUT = '/home/claude/brigada/out/sheets'
os.makedirs(OUT, exist_ok=True)
PITCH = math.degrees(math.atan2(12, 18))  # game camera pitch


def loop_times(dur, n):
    return [dur * i / n for i in range(n)]


def lin(a, b, n, end=True):
    if n == 1: return [a]
    return [a + (b - a) * i / (n - 1 if end else n) for i in range(n)]


def seg_times(t0, timp, t1, na, nb):
    """na frames from t0 up to timp (inclusive), nb frames after timp up to t1 (inclusive)."""
    pre = lin(t0, timp, na)
    post = [timp + (t1 - timp) * (i + 1) / nb for i in range(nb)]
    return pre + post, na - 1


def sharpen(im, k, sigma=1.0):
    """Realce de detalle (máscara de enfoque) sin halos en el borde: el desenfoque se pondera por el alfa."""
    import numpy as np
    from scipy.ndimage import gaussian_filter
    a = np.asarray(im).astype(np.float32) / 255; rgb, al = a[..., :3], a[..., 3:4]
    w = gaussian_filter(al[..., 0], sigma)[..., None] + 1e-4
    blur = np.stack([gaussian_filter(rgb[..., c] * al[..., 0], sigma) for c in range(3)], -1) / w
    out = np.clip(rgb + k * (rgb - blur) * (al > 0.02), 0, 1)
    return Image.fromarray((np.concatenate([out, al], -1) * 255 + .5).astype(np.uint8), 'RGBA')


def smooth(x):
    x = max(0.0, min(1.0, x)); return x * x * (3 - 2 * x)


HCFG = {}


def guard_sched(sheet, t):
    """(bend, grav, side) for the hammer at clip time t."""
    WB, WG, WS = 42.0, 0.85, 190.0         # transporte: cuelga de la mano, hacia atrás y apenas hacia adentro (detrás de la pierna)
    if sheet in ('guard_walk', 'guard_stand'):
        return WB, WG, WS
    timp = HCFG['timp']; aimp = HCFG['aimp']; TOPB = -20.0
    if t >= 1.5:  # regreso: primero se endereza (curva 0, sin giro lateral) y luego vuelve a colgar
        u = (t - 1.5) / 0.85
        if u < 0.5: return aimp * (1 - smooth(u / 0.5)), WG * 0.85 * smooth(u / 0.5), 0.0
        v = smooth((u - 0.5) / 0.5)
        return WB * v, WG * (0.85 + 0.15 * v), WS
    if t < 0.12: b = WB
    elif t < 0.72: b = WB + (TOPB - WB) * smooth((t - 0.12) / 0.6)
    elif t < timp: b = TOPB + (aimp - TOPB) * smooth((t - 0.72) / max(0.05, timp - 0.72))
    elif t < 1.5: b = aimp
    else: b = aimp + (WB - aimp) * smooth((t - 1.5) / 0.85)
    if t < 0.1: k = 0.0
    elif t < 0.45: k = smooth((t - 0.1) / 0.35)
    elif t < 1.5: k = 1.0
    else: k = 1 - smooth((t - 1.5) / 0.85)
    return b, WG * (1 - k), WS * (1 - k)


CHARS = {
    'sol': dict(model='/in/mx/sol_run.fbx', clips=['/in/mx/sol_run.fbx'], tex='t_c6c82a8a', inplace=[True], yaw=180, mirror=False,
                shadow=True, bodyPx=128, rifle=True,
                sheets=[dict(key='sol0', ci=0, frames=16, mode='fixed', loop=True)]),
    'zomA': dict(model='/in/mx/zom_run.fbx', clips=['/in/mx/zom_run.fbx'], tex='t_63b242d2', inplace=[True], yaw=0, mirror=False,
                 shadow=True, bodyPx=120, sheets=[dict(key='zom0', ci=0, frames=16, mode='fixed', loop=True)]),
    'zomB': dict(model='/in/mx/zom2_rig.fbx', clips=['/in/mx/zom_run.fbx'], tex='t_9227c39d', inplace=[True], yaw=0, mirror=False,
                 shadow=True, bodyPx=120, sheets=[dict(key='zom1', ci=0, frames=16, mode='fixed', loop=True)]),
    'zomC': dict(model='/in/mx/zom3_run.fbx', clips=['/in/mx/zom3_run.fbx'], tex='t_787203a8', inplace=[True], yaw=0, mirror=False,
                 shadow=True, bodyPx=120, sheets=[dict(key='zom2', ci=0, frames=16, mode='fixed', loop=True)]),
    'zomD': dict(model='/in/mx/zom4_run.fbx', clips=['/in/mx/zom4_run.fbx'], tex='t_2a27725a', inplace=[True], yaw=0, mirror=False,
                 shadow=True, bodyPx=120, sheets=[dict(key='zom3', ci=0, frames=16, mode='fixed', loop=True)]),
    'zomE': dict(model='/in/mx/zom5_run.fbx', clips=['/in/mx/zom5_run.fbx'], tex='t_8ad1c09f', inplace=[True], yaw=0, mirror=False,
                 shadow=True, bodyPx=120, sheets=[dict(key='zom4', ci=0, frames=16, mode='fixed', loop=True)]),
    'solB': dict(model='/in/mx/sol2_run.fbx', clips=['/in/mx/sol2_run.fbx'], tex='t_9a6454e7', inplace=[True], yaw=180, mirror=False,
                 shadow=True, bodyPx=128, rifle=True, sheets=[dict(key='sol1', ci=0, frames=16, mode='fixed', loop=True)]),
    'bru': dict(model='/in/mx/bru_run.fbx', clips=['/in/mx/bru_run.fbx', '/in/mx/bru_punch.fbx'], tex='t_339788cb', inplace=[True, True], yaw=0, mirror=False,
                shadow=True, bodyPx=150, sheets=[dict(key='bru0', ci=0, frames=16, mode='fixed', loop=True),
                                                 dict(key='brup0', ci=1, frames=24, mode='fixed', loop=True)]),
    'titan': dict(model='/in/mx/x_walk.fbx', clips=['/in/mx/x_walk.fbx', '/in/mx/x_jump.fbx', '/in/mx/x_swipe.fbx', '/in/mx/x_stand.fbx'],
                  # 360 px de cuerpo: en pantalla se dibuja a ~290-460 px, así se ve casi 1:1 (antes 240 px: ampliado hasta 2x, borroso)
                  tex='t_55648842', inplace=[False, True, True, [1.0, 0.0]], yscale=[0, 0.25, 0, 0], yaw=0, mirror=False, shadow=False, bodyPx=360, chest=True, sharpen=0.55,
                  sheets=[dict(key='titan_walk', ci=0, frames=20, mode='fixed', loop=True),
                          dict(key='titan_atk', ci=1, mode='trim', seg=(0.15, None, 3.0, 16, 14)),
                          dict(key='titan_swipe', ci=2, mode='trim', span=(0.0, 2.25, 16)),
                          dict(key='titan_rise', ci=3, mode='trim', span=(0.5, 2.6, 16))]),
    # caminata y golpe de arma pesada a dos manos (Great Sword de Mixamo); el despertar sigue con "Crouch Turn To Stand"
    'guard': dict(model='/in/mx/grd_gs_walk.fbx', clips=['/in/mx/grd_gs_walk.fbx', '/in/mx/grd_stand.fbx', '/in/mx/grd_gs_jump.fbx'], tex='t_82c0393d',
                  inplace=[True, True, True], two=('LeftHand', 'RightHand'), sharpen=0.4, yaw=180, mirror=True, shadow=False, bodyPx=240, hammer=True, hammer_glb='/in/glb/p_a576b4a2.glb',
                  sheets=[dict(key='guard_walk', ci=0, frames=24, mode='fixed', loop=True),
                          dict(key='guard_stand', ci=1, mode='trim', span=(0.34, None, 30), rootYaw=180),
                          dict(key='guard_atk', ci=2, mode='trim', seg=(0.0, None, 2.17, 18, 18))]),
}


async def find_impact(b, ch, info):
    """Clip time of the main hit for attack clips."""
    if ch == 'guard':
        # golpe: el instante en que la cabeza del martillo (agarre a dos manos) llega más abajo
        await b.js('([a,c])=>B.setTwo(a,c)', list(CHARS['guard']['two']))
        best = None
        for i in range(81):
            t = 0.95 + 0.6 * i / 80
            await b.js('([c,t])=>B.pose(c,t)', [2, t]); p = await b.js('()=>B.hammerHead()')
            if best is None or p[1] < best[1]: best = (t, p[1])
        print('guard impacto t=%.3f cabeza y=%.2f' % best)
        return best[0]
    if ch == 'titan':
        best = None
        for i in range(81):
            t = 1.3 + 0.6 * i / 80
            await b.js('([c,t])=>B.pose(c,t)', [1, t])
            a = await b.js('()=>B.boneWorld("RightHand")'); c = await b.js('()=>B.boneWorld("LeftHand")')
            y = min(a[1], c[1])
            if best is None or y < best[1] - 1e-6: best = (t, y)
        return best[0]


async def pose_full(b, ch, sheet, ci, t, rootYaw):
    if ch == 'guard':
        if sheet['key'] in ('guard_walk', 'guard_atk'):
            # dos manos: el mango pasa por ambos puños; la cara del martillo mira hacia donde va el golpe
            await b.js('([a,c])=>B.setTwo(a,c)', list(CHARS['guard']['two']))
            await b.js('(y)=>B.setRootYaw(y)', rootYaw)
            dt = 0.035
            await b.js('([c,t])=>B.pose(c,t)', [ci, max(0, t - dt)]); h0 = await b.js('()=>B.hammerHead()')
            await b.js('([c,t])=>B.pose(c,t)', [ci, t + dt]); h1 = await b.js('()=>B.hammerHead()')
            await b.js('(v)=>B.setVel(v)', [h1[i] - h0[i] for i in range(3)])
        else:
            await b.js('()=>B.setTwo(null)')
            bend, grav, side = guard_sched(sheet['key'], t)
            await b.js('([a,g,s])=>{B.setBend(a);B.setGrav(g);B.setSide(s);}', [bend, grav, side])
    await b.js('(y)=>B.setRootYaw(y)', rootYaw)
    await b.js('([c,t])=>B.pose(c,t)', [ci, t])


async def bake_char(b, ch):
    C = CHARS[ch]
    info = await b.js('([m,c,t,o])=>B.load(m,c,t,o)', [C['model'], C['clips'], tex_for(C['tex']), {'inPlace': C['inplace'], 'yScale': C.get('yscale')}])
    durs = [c['dur'] for c in info['clips']]
    await b.js(open('/home/claude/brigada/viewer/hooks.js').read())
    await b.js('(y)=>B.view(y,%f)' % PITCH, C['yaw'])
    await b.js('([c,t])=>B.pose(c,t)', [0, 0])
    Hm = (await b.js('()=>B.boneWorld("HeadTop_End")'))[1]
    meta_char = {'H_model': Hm}
    if C.get('rifle'):
        await b.js('([s,g])=>B.setupRifle(s,g)', [Hm / 1.75, [0, 0, 0]])
    if C.get('hammer'):
        hand = await b.js('()=>B.boneWorld("RightHand")'); idx = await b.js('()=>B.boneWorld("RightHandIndex1")')
        L = 0.46 * Hm   # martillo más grande para un robot gigante
        if C.get('hammer_glb'):
            print('hammer glb', await b.js('([u,h,f,l,k])=>B.setupHammerGLB(u,h,f,l,k)', [C['hammer_glb'], 'RightHand', 'RightForeArm', L, 1.35]))
        else:
            await b.js('([h,f,l])=>B.setupHammer(h,f,l)', ['RightHand', 'RightForeArm', L])
        await b.js('(g)=>B.setGrip(g)', 0.6 * math.dist(hand, idx))
        await b.js('()=>{B.att.hammer.minY=0.13;}')  # la cabeza puede apoyarse en el suelo (arrastre)
        HCFG['timp'] = await find_impact(b, ch, info)
        # bend at impact so the head rests on the ground
        best = None
        for a in range(-40, 96, 5):
            await b.js('([a,g])=>{B.setBend(a);B.setGrav(g);B.setSide(0);}', [a, 0.0]); await b.js('([c,t])=>B.pose(c,t)', [2, HCFG['timp']])
            hy = (await b.js('()=>B.hammerHead()'))[1]
            if best is None or abs(hy - 0.17 * L) < abs(best[1] - 0.17 * L): best = (a, hy)
        HCFG['aimp'] = float(best[0])
        meta_char.update({'hammerL': L, 'timp': HCFG['timp'], 'aimp': HCFG['aimp']})
        print('guard impact', HCFG)
    timp_titan = await find_impact(b, ch, info) if ch == 'titan' else None
    # pixels per unit from walk/run body height
    hs = []
    for t in loop_times(durs[0], 8):
        await pose_full(b, ch, C['sheets'][0], 0, t, 0)
        x0, x1, y0, y1 = await b.js('()=>B.bounds(11,false)')
        hs.append(y1 - min(0, y0))
    hs.sort(); hb = hs[len(hs) // 2]
    ppu = C['bodyPx'] / hb
    print(ch, 'H_model %.1f body cam-height %.1f ppu %.3f' % (Hm, hb, ppu))
    results = {}
    for sh in C['sheets']:
        ci = sh['ci']; dur = durs[ci]; rootYaw = sh.get('rootYaw', 0)
        impF = None
        if sh.get('loop'): times = loop_times(dur, sh['frames'])
        elif 'seg' in sh:
            t0, timp, t1, na, nb = sh['seg']
            timp = HCFG['timp'] if ch == 'guard' else timp_titan
            times, impF = seg_times(t0, timp, min(t1, dur), na, nb)
        else:
            a, e, n = sh['span']; times = lin(a, min(e or dur, dur), n)
        # pass 1: bounds
        U = [1e9, -1e9, 1e9, -1e9]; UB = [1e9, -1e9, 1e9, -1e9]
        for t in times:
            await pose_full(b, ch, sh, ci, t, rootYaw)
            bb = await b.js('()=>B.bounds(9,true)'); bo = await b.js('()=>B.bounds(9,false)')
            for i, f in enumerate((min, max, min, max)):
                U[i] = f(U[i], bb[i]); UB[i] = f(UB[i], bo[i])
        pad = 6
        if C['shadow']:
            U[1] += 0.2 * hb; U[0] -= 0.1 * hb; U[2] -= 0.1 * hb
        left = math.floor(U[0] * ppu) - pad; right = math.ceil(U[1] * ppu) + pad
        top = math.ceil(U[3] * ppu) + pad; bot = math.floor(min(U[2], 0) * ppu) - pad
        W = right - left; H = top - bot; ox = -left; oy = top
        frames = []; extras = []
        for t in times:
            await pose_full(b, ch, sh, ci, t, rootYaw)
            d = await b.js('([l,r,t,bt,w,h,s])=>B.frame(l,r,t,bt,w,h,s)', [left / ppu, right / ppu, top / ppu, bot / ppu, W, H, C['shadow']])
            im = img_of(d)
            ex = {}
            pts = {}
            if C.get('rifle'): pts['m'] = await b.js('()=>B.muzzle()')
            if C.get('chest'):
                sp = await b.js('()=>B.boneWorld("Spine2")'); hp = await b.js('()=>B.boneWorld("Hips")')
                q = await b.js('()=>B.boneQuat("Spine2")')
                pts['c'] = sp  # refined below with forward offset
            if C.get('hammer'): pts['h'] = await b.js('()=>B.hammerFace()'); pts['hh'] = await b.js('()=>B.hammerHead()')
            for k, p in pts.items():
                cx, cy = await b.js('(p)=>B.toCam(p)', p)
                px = ox + cx * ppu; py = oy - cy * ppu
                if C['mirror']: px = W - px
                ex[k] = (px, py)
                ex[k + '_w'] = p
            if C['mirror']: im = ImageOps.mirror(im)
            if C.get('sharpen'): im = sharpen(im, C['sharpen'])
            frames.append(im); extras.append(ex)
        oxm = (W - ox) if C['mirror'] else ox
        body_top_px = oy - UB[3] * ppu
        # crop / pack
        if sh['mode'] == 'fixed':
            bx = [im.getbbox() for im in frames]
            x0 = max(0, min(b_[0] for b_ in bx) - 1); y0 = max(0, min(b_[1] for b_ in bx) - 1)
            x1 = min(W, max(b_[2] for b_ in bx) + 1); y1 = min(H, max(b_[3] for b_ in bx) + 1)
            # keep anchor horizontally centered for symmetric scaling
            half = max(oxm - x0, x1 - oxm); x0 = int(max(0, math.floor(oxm - half))); x1 = int(min(W, math.ceil(oxm + half)))
            cells = [im.crop((x0, y0, x1, y1)) for im in frames]
            cw, chh = x1 - x0, y1 - y0
            m = {'fw': cw, 'fh': chh, 'ax': round(oxm - x0, 2), 'ay': round(oy - y0, 2), 'top': round(body_top_px - y0, 2)}
            offs = [(x0, y0)] * len(frames)
        else:
            bx = [im.getbbox() or (0, 0, 1, 1) for im in frames]
            offs = [(max(0, b_[0] - 1), max(0, b_[1] - 1)) for b_ in bx]
            sizes = [(min(W, b_[2] + 1) - o[0], min(H, b_[3] + 1) - o[1]) for b_, o in zip(bx, offs)]
            cw = max(s[0] for s in sizes); chh = max(s[1] for s in sizes)
            cells = [im.crop((o[0], o[1], o[0] + cw, o[1] + chh)) for im, o in zip(frames, offs)]
            m = {'fw': cw, 'fh': chh, 'axs': [round(oxm - o[0], 1) for o in offs], 'ays': [round(oy - o[1], 1) for o in offs]}
            m['ax'] = round(sum(m['axs']) / len(m['axs']), 1); m['ay'] = round(sum(m['ays']) / len(m['ays']), 1)
            m['top'] = round(body_top_px - min(o[1] for o in offs), 1)
        n = len(cells)
        cols = max(1, min(n, 4096 // cw)); rows = (n + cols - 1) // cols
        sheet = Image.new('RGBA', (cols * cw, rows * chh), (0, 0, 0, 0))
        for i, c in enumerate(cells):
            sheet.paste(c, ((i % cols) * cw, (i // cols) * chh))
        m.update({'n': n, 'cols': cols, 'ppu': ppu})
        if impF is not None: m['impF'] = impF
        if C.get('rifle'):
            mx = [e['m'][0] - o[0] for e, o in zip(extras, offs)]; my = [e['m'][1] - o[1] for e, o in zip(extras, offs)]
            m['mx'] = round(sum(mx) / n, 2); m['my'] = round(sum(my) / n, 2)
        if C.get('chest'):
            m['mxs'] = [round(e['c'][0] - o[0], 1) for e, o in zip(extras, offs)]; m['mys'] = [round(e['c'][1] - o[1], 1) for e, o in zip(extras, offs)]
        if C.get('hammer') and impF is not None:
            cand = range(max(0, impF - 2), min(n, impF + 5))
            impF = min(cand, key=lambda i: extras[i]['hh_w'][1]); m['impF'] = impF
            # impact point in model units relative to root (x mirrored -> screen right positive), z forward
            hw = extras[impF]['hh_w']
            m['impW'] = [round(hw[0] if C['mirror'] else -hw[0], 2), round(hw[2], 2)]  # screen-right positive
        if sh['key'] == 'guard_atk' or sh['key'] == 'titan_atk':
            m['clip'] = [round(times[0], 3), round(times[impF], 3), round(times[-1], 3)]
        m['h_model'] = Hm
        sheet.save(os.path.join(OUT, sh['key'] + '.png'))
        json.dump(m, open(os.path.join(OUT, sh['key'] + '.json'), 'w'))
        print('  %-12s n=%2d cell %dx%d grid %dx%d sheet %dx%d impF=%s' % (sh['key'], n, cw, chh, cols, rows, sheet.width, sheet.height, impF))
        results[sh['key']] = m
    json.dump(meta_char, open(os.path.join(OUT, '_%s.json' % ch), 'w'))
    return results


async def main():
    which = sys.argv[1:] or list(CHARS)
    async with Baker() as b:
        for ch in which:
            await bake_char(b, ch)
        errs = [e for e in b.errs if '404' not in e]
        print('errors', errs[:5])

asyncio.run(main())
