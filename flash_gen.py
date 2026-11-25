"""Realistic muzzle flash sprites (4 variants), seen from behind the shooter: forward plume + side petals."""
import numpy as np, os, json
from PIL import Image, ImageFilter
OUT = '/home/claude/brigada/out/fx'; os.makedirs(OUT, exist_ok=True)
rng = np.random.default_rng(5)
S = 128
yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
cx, cy = S / 2, S * 0.56
X = (xx - cx) / (S / 2); Y = (yy - cy) / (S / 2)
D = np.sqrt(X * X + Y * Y) + 1e-6; A = np.arctan2(Y, X)
LAT = rng.random((32, 32)).astype(np.float32)
def vn(x, y):
    xi = np.floor(x).astype(int); yi = np.floor(y).astype(int); xf = x - xi; yf = y - yi
    u = xf * xf * (3 - 2 * xf); v = yf * yf * (3 - 2 * yf)
    a = LAT[xi % 32, yi % 32]; b = LAT[(xi + 1) % 32, yi % 32]; c = LAT[xi % 32, (yi + 1) % 32]; d = LAT[(xi + 1) % 32, (yi + 1) % 32]
    return (a + (b - a) * u) * (1 - v) + (c + (d - c) * u) * v
def ramp(T):
    stops = [(0, (0, 0, 0)), (.18, (120, 26, 6)), (.38, (230, 90, 20)), (.6, (255, 170, 60)), (.82, (255, 232, 160)), (1, (255, 255, 245))]
    T = np.clip(T, 0, 1); o = np.zeros(T.shape + (3,), np.float32)
    for (t0, c0), (t1, c1) in zip(stops[:-1], stops[1:]):
        m = (T >= t0) & (T <= t1); k = ((T - t0) / (t1 - t0))[m][:, None]; o[m] = np.array(c0) * (1 - k) + np.array(c1) * k
    return o
frames = []
for v in range(4):
    r = 0.2 + 0.05 * rng.random()
    lobes = [(-np.pi / 2 + rng.normal(0, .08), 0.7 + 0.18 * rng.random(), 0.3)]          # forward plume (up)
    k = 4 + v % 2
    for i in range(k):
        ang = -np.pi / 2 + (i + 0.5) / k * 2 * np.pi + rng.normal(0, .15)
        lobes.append((ang, 0.24 + 0.26 * rng.random(), 0.19 + 0.07 * rng.random()))
    R = np.full_like(D, r)
    for ang, ln, wd in lobes:
        da = np.angle(np.exp(1j * (A - ang)))
        R = np.maximum(R, r + ln * np.exp(-(da / wd) ** 2))
    n = vn(X * 6 + v * 9, Y * 6 + v * 3) * 0.55 + vn(X * 14 + v, Y * 14) * 0.45
    q = 1 - D / (R * (0.85 + 0.3 * n))
    core = np.clip(1 - D / (r * 0.9), 0, 1) ** 1.2
    T = np.clip(q, 0, 1) ** 0.8 * (0.75 + 0.35 * n) + core * 0.7
    col = ramp(T)
    glow = np.exp(-(D / 0.5) ** 2) * 0.35
    col = np.clip(col + np.array([255, 150, 60]) * glow[..., None] * 0.6, 0, 255)
    alpha = np.clip(T * 1.4 + glow * 0.8, 0, 1)
    im = Image.fromarray(np.dstack([col, alpha * 255]).astype(np.uint8), 'RGBA').filter(ImageFilter.GaussianBlur(0.6))
    frames.append(im)
sheet = Image.new('RGBA', (S * 4, S), (0, 0, 0, 0))
for i, f in enumerate(frames): sheet.paste(f, (i * S, 0))
sheet.save(os.path.join(OUT, 'flash.png'))
m = json.load(open(os.path.join(OUT, 'fx.json'))); m['flash'] = {'fw': S, 'fh': S, 'n': 4, 'cols': 4, 'cy': 0.56}
json.dump(m, open(os.path.join(OUT, 'fx.json'), 'w')); print('ok')
