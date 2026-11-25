"""Seamless road/sidewalk tiles and the skyline strip from the Gemini images."""
import numpy as np, os
from PIL import Image, ImageFilter
D = '/mnt/user-data/uploads/Downloads/'
OUT = '/home/claude/brigada/out/tex'; os.makedirs(OUT, exist_ok=True)


def seamless(path, size, mean_target, contrast):
    im = Image.open(path).convert('RGB').resize((size, size), Image.LANCZOS)
    a = np.array(im).astype(np.float32)
    h, w = a.shape[:2]
    b = np.roll(np.roll(a, h // 2, 0), w // 2, 1)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    # weight: 1 in the centre of the original, 0 at its borders
    wx = 1 - np.abs((xx + .5) / w * 2 - 1); wy = 1 - np.abs((yy + .5) / h * 2 - 1)
    m = np.clip(np.minimum(wx, wy) * 3.2, 0, 1)[..., None]
    c = a * m + b * (1 - m)
    # luminance-normalise for multiply blending (keeps palette hue from the game)
    lum = c.mean(-1, keepdims=True)
    g = (lum - lum.mean()) * contrast + mean_target * 255
    c = np.clip(np.concatenate([g, g, g], -1) * 0.75 + c / c.mean() * mean_target * 255 * 0.25, 0, 255)
    return Image.fromarray(c.astype(np.uint8))


road = seamless(D + 'Gemini_Generated_Image_dxvrg1dxvrg1dxvr.jpg', 256, 0.80, 1.05); road.save(os.path.join(OUT, 'road.png'))
walk = seamless(D + 'Gemini_Generated_Image_5oqo2b5oqo2b5oqo.jpg', 256, 0.84, 0.95); walk.save(os.path.join(OUT, 'walk.png'))
# skyline strip 1600x320, top faded to transparent
sk = Image.open(D + 'Gemini_Generated_Image_8e0d3i8e0d3i8e0d.jpg').convert('RGB')
W0, H0 = sk.size
crop = sk.crop((0, int(H0 * 0.12), W0, H0)).resize((1600, 320), Image.LANCZOS)
a = np.array(crop).astype(np.float32)
lum = a.mean(-1)
# buildings are darker than the sky: alpha from vertical position and darkness
yy = np.mgrid[0:320, 0:1600][0].astype(np.float32) / 320
vert = np.clip((yy - 0.18) / 0.32, 0, 1)
dark = np.clip((lum.max() * 0.92 - lum) / (lum.max() * 0.35), 0, 1)
alpha = np.clip(np.maximum(vert * 0.85, dark * np.clip(yy * 2.2, 0, 1)), 0, 1)
alpha = np.array(Image.fromarray((alpha * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.5))).astype(np.float32) / 255
out = np.dstack([a, alpha * 255]).astype(np.uint8)
Image.fromarray(out, 'RGBA').save(os.path.join(OUT, 'sky.png'))
print('ok', road.size, walk.size)
