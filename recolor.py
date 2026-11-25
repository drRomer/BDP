"""Lime hi-vis vest variant of a brute sheet: recolor.py src.png dst.png"""
import sys, numpy as np
from PIL import Image
im = Image.open(sys.argv[1]).convert('RGBA'); a = np.array(im).astype(np.float32) / 255
rgb = a[..., :3]; mx = rgb.max(-1); mn = rgb.min(-1); d = mx - mn + 1e-6
r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
h = np.where(mx == r, ((g - b) / d) % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) * 60
s = d / (mx + 1e-6); v = mx
mask = (h > 2) & (h < 32) & (s > 0.45) & (v > 0.22) & (a[..., 3] > 0)
h2 = np.where(mask, h + 52, h) % 360
c = v * s; x = c * (1 - np.abs((h2 / 60) % 2 - 1)); m = v - c; hi = (h2 // 60).astype(int) % 6; z = 0 * c
out = np.zeros_like(rgb)
for k, (R, G, B) in enumerate([(c, x, z), (x, c, z), (z, c, x), (z, x, c), (x, z, c), (c, z, x)]):
    sel = hi == k; out[..., 0][sel] = (R + m)[sel]; out[..., 1][sel] = (G + m)[sel]; out[..., 2][sel] = (B + m)[sel]
res = np.concatenate([np.where(mask[..., None], out, rgb), a[..., 3:]], -1)
Image.fromarray((res * 255).clip(0, 255).astype(np.uint8)).save(sys.argv[2]); print(sys.argv[2], int(mask.sum()))
