"""Playwright helper around viewer/bake.html."""
import asyncio, base64, io, json, os, subprocess, time, socket
from PIL import Image
from playwright.async_api import async_playwright

ROOT = '/home/claude/brigada'
PORT = 8931


def ensure_server():
    s = socket.socket()
    try:
        s.connect(('127.0.0.1', PORT)); s.close(); return
    except OSError:
        pass
    subprocess.Popen(['python3', '-m', 'http.server', str(PORT), '--bind', '127.0.0.1'], cwd=ROOT,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.0)


def tex_for(folder):
    """Find Tripo PBR maps in an extracted zip folder -> URLs."""
    d = os.path.join(ROOT, 'in', folder)
    out = {}
    for dp, _, fs in os.walk(d):
      for f in fs:
        lf = f.lower()
        u = '/' + os.path.relpath(os.path.join(dp, f), ROOT).replace(os.sep, '/')
        if 'basecolor' in lf: out['base'] = u
        elif 'normal' in lf: out['normal'] = u
        elif 'roughness' in lf: out['rough'] = u
        elif 'metallic' in lf: out['metal'] = u
    return out


def img_of(data_url):
    return Image.open(io.BytesIO(base64.b64decode(data_url.split(',', 1)[1]))).convert('RGBA')


class Baker:
    async def __aenter__(self):
        ensure_server()
        self.pw = await async_playwright().start()
        self.br = await self.pw.chromium.launch(executable_path='/usr/bin/google-chrome',
                                                args=['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'])
        self.pg = await self.br.new_page(viewport={'width': 600, 'height': 600})
        self.errs = []
        self.pg.on('pageerror', lambda e: self.errs.append(str(e)))
        self.pg.on('console', lambda m: self.errs.append(m.text) if m.type == 'error' else None)
        await self.pg.goto('http://127.0.0.1:%d/viewer/bake.html' % PORT)
        await self.pg.wait_for_function('window.READY===true', timeout=60000)
        return self

    async def __aexit__(self, *a):
        await self.br.close(); await self.pw.stop()

    async def js(self, expr, arg=None):
        return await self.pg.evaluate(expr, arg)
