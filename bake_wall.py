"""Muro lateral del puente: panel de Tripo (p_cb91a752) horneado de frente y recortado de poste a poste para repetirlo sin costuras."""
import asyncio, sys, json
sys.path.insert(0,'/home/claude/brigada')
from bk import Baker, img_of
from PIL import Image
import numpy as np
YAW = 270; PPU = 520
async def main():
    async with Baker() as b:
        bb = await b.js('(u)=>B.loadGLB(u)', '/in/glb/p_cb91a752.glb')
        mn, mx = bb['min'], bb['max']; cx, cz = (mn[0]+mx[0])/2, (mn[2]+mx[2])/2
        await b.js('([p,r,s])=>B.setRootTransform(p,r,s)', [[-cx, -mn[1], -cz], 0, 1])
        await b.js('(y)=>B.view(y,0)', YAW)
        x0, x1, y0, y1 = await b.js('()=>B.bounds(29,false)')
        W = int((x1-x0)*PPU); H = int((y1-y0)*PPU)
        d = await b.js('([l,r,t,bt,w,h,s])=>B.frame(l,r,t,bt,w,h,s)', [x0, x1, y1, y0, W, H, False])
        im = img_of(d); im = im.crop(im.getbbox()); im.save('/tmp/wall_full.png')
    a = np.array(im.convert('RGBA')).astype(float)
    # postes: columnas oscuras en la franja entre los dos rieles (parte alta)
    h = a.shape[0]; band = a[int(h*.1):int(h*.32), :, :3].mean(axis=(0, 2))
    dark = band < np.percentile(band, 25)
    runs = []; s = None
    for i, v in enumerate(dark):
        if v and s is None: s = i
        if not v and s is not None:
            if i-s >= 4: runs.append((s+i)/2)
            s = None
    print('width', im.width, 'height', im.height, 'postes', runs)
    json.dump({'posts': runs, 'w': im.width, 'h': im.height}, open('/tmp/wall_posts.json', 'w'))
asyncio.run(main())
