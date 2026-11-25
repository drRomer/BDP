"""Raymarched fireball + smoke puff sprites rendered with WebGL (viewer/fx.html)."""
import asyncio, sys, os, json, base64, io
sys.path.insert(0, '/home/claude/brigada')
from bk import ensure_server, PORT
from playwright.async_api import async_playwright
from PIL import Image
OUT = '/home/claude/brigada/out/fx'; os.makedirs(OUT, exist_ok=True)

def img(d): return Image.open(io.BytesIO(base64.b64decode(d.split(',', 1)[1]))).convert('RGBA')

def sheet(frames, cols):
    S = frames[0].width; n = len(frames); rows = (n + cols - 1) // cols
    im = Image.new('RGBA', (cols * S, rows * S), (0, 0, 0, 0))
    for i, f in enumerate(frames): im.paste(f, ((i % cols) * S, (i // cols) * S))
    return im

async def main():
    ensure_server()
    async with async_playwright() as p:
        br = await p.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'])
        pg = await br.new_page(); errs = []
        pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' else None)
        await pg.goto('http://127.0.0.1:%d/viewer/fx.html' % PORT)
        await pg.wait_for_function('window.READY===true', timeout=60000)
        N = 24
        fire = [img(await pg.evaluate('(a)=>FX.frame(...a)', [192, i / (N - 1), 3.0, 1.0, 0.18, 0.62, 2.0, 1.0])) for i in range(N)]
        sheet(fire, 8).save(os.path.join(OUT, 'fire.png'))
        puffs = [img(await pg.evaluate('(a)=>FX.frame(...a)', [128, 0.42, 10.0 + k * 7, 0.0, 0.0, 0.62, 1.5, 1.35])) for k in range(4)]
        sheet(puffs, 4).save(os.path.join(OUT, 'smoke.png'))
        json.dump({'fire': {'fw': 192, 'fh': 192, 'n': N, 'cols': 8}, 'smoke': {'fw': 128, 'fh': 128, 'n': 4, 'cols': 4}}, open(os.path.join(OUT, 'fx.json'), 'w'))
        print('errors', errs[:3])
        await br.close()

asyncio.run(main())
