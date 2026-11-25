"""Procedural FX sprites: fireball explosion sheet + smoke puffs (numpy fbm noise)."""
import numpy as np, os, json
from PIL import Image
OUT = '/home/claude/brigada/out/fx'; os.makedirs(OUT, exist_ok=True)
rng = np.random.default_rng(7)
LAT = rng.random((64, 64, 64)).astype(np.float32)


def vnoise(x, y, z):
    xi = np.floor(x).astype(int); yi = np.floor(y).astype(int); zi = np.floor(z).astype(int)
    xf = x - xi; yf = y - yi; zf = z - zi
    u = xf * xf * (3 - 2 * xf); v = yf * yf * (3 - 2 * yf); w = zf * zf * (3 - 2 * zf)
    def L(a, b, c): return LAT[a % 64, b % 64, c % 64]
    c000 = L(xi, yi, zi); c100 = L(xi + 1, yi, zi); c010 = L(xi, yi + 1, zi); c110 = L(xi + 1, yi + 1, zi)
    c001 = L(xi, yi, zi + 1); c101 = L(xi + 1, yi, zi + 1); c011 = L(xi, yi + 1, zi + 1); c111 = L(xi + 1, yi + 1, zi + 1)
    x00 = c000 + (c100 - c000) * u; x10 = c010 + (c110 - c010) * u; x01 = c001 + (c101 - c001) * u; x11 = c011 + (c111 - c011) * u
    y0 = x00 + (x10 - x00) * v; y1 = x01 + (x11 - x01) * v
    return y0 + (y1 - y0) * w


def fbm(x, y, z, oct=5):
    s = 0; a = 0.5; f = 1.0; tot = 0
    for _ in range(oct):
        s += a * vnoise(x * f, y * f, z * f); tot += a; a *= 0.5; f *= 2.03
    return s / tot


def ramp(T):
    # temperature -> color
    stops = [(0.0, (52, 48, 46)), (0.18, (78, 54, 44)), (0.35, (170, 62, 26)), (0.55, (240, 120, 36)), (0.75, (255, 186, 80)), (0.92, (255, 238, 190)), (1.0, (255, 252, 238))]
    T = np.clip(T, 0, 1); out = np.zeros(T.shape + (3,), np.float32)
    for (t0, c0), (t1, c1) in zip(stops[:-1], stops[1:]):
        m = (T >= t0) & (T <= t1); k = ((T - t0) / (t1 - t0))[m][:, None]
        out[m] = np.array(c0) * (1 - k) + np.array(c1) * k
    return out


def fireball(N=24, S=192):
    frames = []
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
    X = (xx / S) * 2 - 1; Y = (yy / S) * 2 - 1
    for f in range(N):
        t = f / (N - 1)
        R = 0.22 + 0.68 * (1 - (1 - t) ** 2.4)
        Yr = Y + t * 0.28                      # rises
        d = np.sqrt(X * X + (Yr * 1.08) ** 2) / R
        n = fbm(X * 2.6 + 11, Yr * 2.6 + 7, t * 1.8 + 3)
        n2 = fbm(X * 6 + 3, Yr * 6 + 1, t * 2.5 + 9, 3)
        dens = np.clip((1 - d) * 1.9 + (n - 0.5) * 1.8 + (n2 - 0.5) * 0.5, 0, 1)
        fade = 1.0 if t < 0.55 else max(0.0, 1 - (t - 0.55) / 0.45) ** 1.4
        dens = dens * fade
        # light from top-left: self shadow
        sh = np.roll(np.roll(dens, 4, 0), 4, 1)
        shade = np.clip(1 + (dens - sh) * 1.8, 0.55, 1.35)
        heat = np.clip(dens * (1.35 - 1.5 * t) + np.clip(1 - d, 0, 1) * (0.9 - 1.1 * t) + (n - 0.5) * 0.4, 0, 1)
        col = ramp(heat)
        smoke_amt = np.clip((t - 0.25) * 1.6, 0, 1) * (1 - heat)
        col = col * (1 - smoke_amt[..., None]) + np.array([64, 60, 58], np.float32) * smoke_amt[..., None]
        col = np.clip(col * shade[..., None], 0, 255)
        alpha = np.clip(dens * 1.5, 0, 1) ** 0.9
        alpha = alpha * np.clip((1 - np.sqrt(X * X + Y * Y)) * 6, 0, 1)   # keep inside the frame
        frames.append(np.dstack([col, alpha * 255]).astype(np.uint8))
    return frames


def puffs(K=4, S=128):
    out = []
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
    X = (xx / S) * 2 - 1; Y = (yy / S) * 2 - 1
    for k in range(K):
        d = np.sqrt(X * X + Y * Y)
        n = fbm(X * 2.2 + k * 17, Y * 2.2 + k * 5, k * 3.1)
        dens = np.clip((1 - d / 0.85) * 1.6 + (n - 0.5) * 1.6, 0, 1) ** 1.2
        sh = np.roll(np.roll(dens, 5, 0), 5, 1)
        shade = np.clip(0.82 + (dens - sh) * 1.5 - Y * 0.12, 0.45, 1.15)
        g = 200 * shade
        col = np.dstack([g * 1.0, g * 0.985, g * 0.97])
        a = dens * np.clip((1 - d) * 5, 0, 1)
        out.append(np.dstack([np.clip(col, 0, 255), a * 235]).astype(np.uint8))
    return out


def sheet(frames, cols):
    S = frames[0].shape[0]; n = len(frames); rows = (n + cols - 1) // cols
    im = Image.new('RGBA', (cols * S, rows * S), (0, 0, 0, 0))
    for i, f in enumerate(frames):
        im.paste(Image.fromarray(f, 'RGBA'), ((i % cols) * S, (i // cols) * S))
    return im


fb = fireball(); sh = sheet(fb, 8); sh.save(os.path.join(OUT, 'fire.png'))
pf = puffs(); sp = sheet(pf, 4); sp.save(os.path.join(OUT, 'smoke.png'))
json.dump({'fire': {'fw': 192, 'fh': 192, 'n': 24, 'cols': 8}, 'smoke': {'fw': 128, 'fh': 128, 'n': 4, 'cols': 4}}, open(os.path.join(OUT, 'fx.json'), 'w'))
print('fire', sh.size, 'smoke', sp.size)
