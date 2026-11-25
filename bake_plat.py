"""Plataforma con jaula del Guardián (Tripo OBJ) → out/props/plat.png (completa) y platF.png (solo pilares/vigas delanteros),
mismo encuadre y ancla. Uso: python3 bake_plat.py [ancho_en_unidades] [giro_grados]"""
import asyncio, sys, json, math, os
sys.path.insert(0, '/home/claude/brigada')
from bk import Baker, img_of
from PIL import Image

OUT = '/home/claude/brigada/out/props'
PITCH = math.degrees(math.atan2(12, 18))
WIDTH = float(sys.argv[1]) if len(sys.argv) > 1 else 13.5
ROT = float(sys.argv[2]) if len(sys.argv) > 2 else 17.4
PITCHES = [20.0, 27.0, 34.0]   # inclinaciones de cámara: lejos, media distancia, cerca
D = 't_af320455'
# base aplastada al 45 % y pilares estirados 1,33 para que el Guardián arrodillado quepa bajo las vigas
WARP = [2.06 / 7.23, 0.45, 1.33]
SX = 0.8   # más angosta de lado a lado: invade menos la calzada


async def main():
    fs = os.listdir('/home/claude/brigada/in/' + D)
    obj = [f for f in fs if f.endswith('.obj')][0]
    T = {k: next(('/in/%s/%s' % (D, f) for f in fs if f.endswith(suf)), None)
         for k, suf in (('map', 'basecolor.jpg'), ('normal', 'normal.jpg'))}
    async with Baker() as b:
        bb = await b.js('([u,t])=>B.loadOBJ(u,t)', ['/in/%s/%s' % (D, obj), T])
        if WARP: bb = await b.js('([d,s,k])=>B.warpY(d,s,k)', WARP)
        mn, mx = bb['min'], bb['max']; dims = [mx[i] - mn[i] for i in range(3)]
        sc = WIDTH / max(dims[0], dims[2]); cx, cz = (mn[0] + mx[0]) / 2, (mn[2] + mx[2]) / 2
        r = math.radians(ROT); c, s = math.cos(r), math.sin(r)
        px = -(cx * c + cz * s) * sc; pz = -(-cx * s + cz * c) * sc
        await b.js('([p,r,s])=>B.setRootTransform(p,r,s)', [[px * SX, -mn[1] * sc, pz], ROT, sc])
        await b.js('(f)=>B.rootScaleX(f)', SX)
        await b.js('(y)=>B.view(y,%f)' % PITCH, 180)
        H = dims[1] * sc
        deck = await b.js('()=>B.rayDown(0,0)')
        # altura de las vigas: rayo hacia abajo sobre un punto de la viga delantera no sirve sin conocerla; se mide el perfil
        prof = []
        for i in range(0, 41):
            x = -WIDTH / 2 + WIDTH * i / 40
            prof.append(await b.js('([x,z])=>B.rayDown(x,z)', [x, 0.0]))
        print('alto', round(H, 2), 'piso', round(deck or 0, 2), 'perfil', [round(p, 1) if p is not None else None for p in prof])
        # pilares: puntos más altos de una grilla de rayos (los remates sobresalen de las vigas)
        hits = []
        for i in range(61):
            for j in range(61):
                x = -WIDTH * .55 + WIDTH * 1.1 * i / 60; z = -WIDTH * .55 + WIDTH * 1.1 * j / 60
                y = await b.js('([x,z])=>B.rayDown(x,z)', [x, z])
                if y is not None: hits.append((x, z, y))
        top = max(h[2] for h in hits); caps = [h for h in hits if h[2] > top - 0.12]
        cl = []
        for (x, z, y) in caps:
            for c in cl:
                if math.hypot(c[0] / c[2] - x, c[1] / c[2] - z) < WIDTH * 0.09: c[0] += x; c[1] += z; c[2] += 1; break
            else: cl.append([x, z, 1])
        pil = sorted([[round(c[0] / c[2], 2), round(c[1] / c[2], 2)] for c in cl], key=lambda p: math.atan2(p[1], p[0]))
        ring = sorted(h[2] for h in hits if top - 1.2 < h[2] < top - 0.12)
        beam = ring[len(ring) // 2] if ring else top - .4
        print('pilares', len(pil), pil, 'remate', round(top, 2), 'viga', round(beam, 2))
        meta = json.load(open(os.path.join(OUT, 'props.json')))
        for k in [k for k in meta if k.startswith(('plat', 'platF'))]: del meta[k]
        cd0 = None
        for P in PITCHES:
            await b.js('(y)=>B.view(y,%f)' % P, 180)
            x0, x1, y0, y1 = await b.js('()=>B.bounds(29,false)')
            ppu = 520 / max(x1 - x0, y1 - y0); pad = 0.1 * max(x1 - x0, y1 - y0)
            L = x0 - pad; R = x1 + pad * 1.5; Tt = y1 + pad * .5; Bt = min(y0, 0) - pad
            W = int(math.ceil((R - L) * ppu)); Hh = int(math.ceil((Tt - Bt) * ppu))
            await b.js('()=>B.setClip(null)')
            full = img_of(await b.js('([l,r,t,bt,w,h,s])=>B.frame(l,r,t,bt,w,h,s)', [L, R, Tt, Bt, W, Hh, True]))
            cd = await b.js('()=>B.camDir()'); n = math.hypot(*cd); ux, uz = cd[0] / n, cd[1] / n
            R0 = WIDTH * 0.5
            await b.js('(p)=>B.setClip(p)', [[ux, 0, uz, -0.22 * R0], [0, 1, 0, -((deck or 0.6) + 0.45)]])
            front = img_of(await b.js('([l,r,t,bt,w,h,s])=>B.frame(l,r,t,bt,w,h,s)', [L, R, Tt, Bt, W, Hh, False]))
            await b.js('()=>B.setClip(null)')
            ox = -L * ppu; oy = Tt * ppu
            bx = full.getbbox(); full = full.crop(bx); front = front.crop(bx); ox -= bx[0]; oy -= bx[1]
            tag = '%d' % round(P)
            full.save(os.path.join(OUT, 'plat%s.png' % tag)); front.save(os.path.join(OUT, 'platF%s.png' % tag))
            m = {'w': round(full.width / ppu, 3), 'h': round(full.height / ppu, 3), 'axf': round(ox / full.width, 4), 'ayf': round(oy / full.height, 4),
                 'deck': round(deck or 0, 3), 'hgt': round(H, 3), 'R': round(R0, 3), 'rot': ROT, 'pil': pil, 'beam': round(beam, 3), 'pitch': round(P, 2)}
            meta['plat' + tag] = m; meta['platF' + tag] = dict(m)
            print('plat', tag, full.size, {k: m[k] for k in ('w', 'h', 'axf', 'ayf')})
        json.dump(meta, open(os.path.join(OUT, 'props.json'), 'w'), indent=1)
        print('errs', [e for e in b.errs if '404' not in e][:3])

asyncio.run(main())
