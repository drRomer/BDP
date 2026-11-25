"""Realistic-ish sound effects synthesized offline (noise physics + formants + reverb) -> mp3 files.
Each entry: name -> list of variants (mono float arrays)."""
import numpy as np, os, subprocess, json
from scipy import signal
SR = 44100
OUT = '/home/claude/brigada/out/sfx'; os.makedirs(OUT, exist_ok=True)
rng = np.random.default_rng(11)


def t_(d): return np.arange(int(SR * d)) / SR
def nz(d): return rng.standard_normal(int(SR * d))
def env_exp(d, tau, att=0.001):
    t = t_(d); e = np.exp(-t / tau)
    if att > 0: e *= np.clip(t / att, 0, 1)
    return e
def bp(x, lo, hi, o=2): return signal.sosfilt(signal.butter(o, [lo, hi], 'bandpass', fs=SR, output='sos'), x)
def lp(x, f, o=2): return signal.sosfilt(signal.butter(o, f, 'lowpass', fs=SR, output='sos'), x)
def hp(x, f, o=2): return signal.sosfilt(signal.butter(o, f, 'highpass', fs=SR, output='sos'), x)
def pad(x, d): n = int(SR * d); return np.pad(x, (0, max(0, n - len(x))))[:max(n, len(x))]
def mix(*xs):
    n = max(len(x) for x in xs); o = np.zeros(n)
    for x in xs: o[:len(x)] += x
    return o
def at(x, delay, total=None):
    o = np.concatenate([np.zeros(int(SR * delay)), x]); return o
def sweep_sine(f0, f1, d, curve=1.0):
    t = t_(d); f = f0 + (f1 - f0) * (t / d) ** curve; ph = 2 * np.pi * np.cumsum(f) / SR; return np.sin(ph)
def sat(x, k=2.0): return np.tanh(x * k) / np.tanh(k)
def reverb(x, d=1.2, wet=0.18, damp=3500, pre=0.012):
    ir = nz(d) * np.exp(-t_(d) / (d / 5.5)); ir = lp(ir, damp); ir[:int(SR * pre)] = 0; ir /= np.sqrt((ir ** 2).sum()) + 1e-9
    w = signal.fftconvolve(x, ir)[:len(x) + int(SR * d)]
    return mix(x, w * wet)
def modes(freqs, decays, amps, d, strike=0.002):
    t = t_(d); o = np.zeros_like(t)
    for f, dc, a in zip(freqs, decays, amps): o += a * np.sin(2 * np.pi * f * t + rng.random() * 6) * np.exp(-t / dc)
    return o * np.clip(t / strike, 0, 1)
def norm(x, peak=0.9): m = np.max(np.abs(x)) + 1e-9; return x / m * peak
def fade_out(x, d=0.02): n = int(SR * d); x = x.copy(); x[-n:] *= np.linspace(1, 0, n); return x


def gunshot(k):
    crack = hp(nz(0.006), 2500) * env_exp(0.006, 0.0012) * 1.0
    body = bp(nz(0.12), 300 + 60 * k, 2600) * env_exp(0.12, 0.018) * 0.9
    thump = sweep_sine(130 - 8 * k, 48, 0.07, 0.6) * env_exp(0.07, 0.02) * 0.8
    mech = bp(nz(0.03), 3000, 7000) * env_exp(0.03, 0.004) * 0.15
    tail = lp(nz(0.45), 1400) * env_exp(0.45, 0.09, 0.004) * 0.22
    x = mix(crack, body, thump, at(mech, 0.018), tail)
    x = sat(x * 1.6, 1.8)
    return fade_out(norm(reverb(x, 0.9, 0.22, 3000), 0.85))


def zombie_hit(k):
    thud = lp(nz(0.09), 500) * env_exp(0.09, 0.02) * 1.0
    squish = bp(nz(0.16), 700, 2400) * env_exp(0.16, 0.035, 0.004) * 0.45
    # short groan with formants
    d = 0.32; t = t_(d); f0 = (105 - 12 * k) * (1 - 0.25 * t / d)
    ph = 2 * np.pi * np.cumsum(f0) / SR; src = signal.sawtooth(ph) + 0.4 * nz(d) * 0.3
    v = mix(bp(src, 450, 800) * 1.0, bp(src, 950, 1300) * 0.6, bp(src, 2300, 2800) * 0.25)
    v *= env_exp(d, 0.12, 0.02)
    x = mix(thud, squish, at(sat(v * 2, 2) * 0.55, 0.02))
    return fade_out(norm(reverb(x, 0.6, 0.12), 0.8))


def grunt(k):
    d = 0.26; t = t_(d); f0 = (150 + 15 * k) * (1.05 - 0.2 * t / d)
    ph = 2 * np.pi * np.cumsum(f0 + 6 * np.sin(2 * np.pi * 9 * t)) / SR
    src = signal.sawtooth(ph, 0.1) + 0.25 * nz(d)
    v = mix(bp(src, 550, 850), bp(src, 1050, 1400) * 0.7, bp(src, 2400, 3000) * 0.3)
    x = sat(v * env_exp(d, 0.09, 0.012) * 2.5, 2.2)
    x = mix(x, lp(nz(0.05), 400) * env_exp(0.05, 0.012) * 0.6)
    return fade_out(norm(reverb(x, 0.5, 0.12), 0.7))


def coin(k):
    f = 2600 + 380 * k
    x = modes([f, f * 2.76, f * 5.4, f * 1.51], [0.12, 0.07, 0.03, 0.09], [1, .5, .25, .35], 0.32)
    x = mix(x, hp(nz(0.004), 4000) * 0.6)
    return fade_out(norm(reverb(x, 0.5, 0.1), 0.45))


def ping(k):
    f = 1800 + 500 * k
    x = modes([f, f * 2.32, f * 3.9], [0.05, 0.03, 0.015], [1, .45, .2], 0.18)
    x = mix(x, bp(nz(0.01), 3000, 9000) * env_exp(0.01, 0.002) * 0.8)
    return fade_out(norm(x, 0.4))


def crate_break():
    parts = [lp(nz(0.08), 1800) * env_exp(0.08, 0.015) * 1.0]
    for i in range(7):
        dl = 0.02 + rng.random() * 0.25
        parts.append(at(bp(nz(0.05), 600 + rng.random() * 1500, 3000 + rng.random() * 2000) * env_exp(0.05, 0.008) * (0.3 + rng.random() * 0.4), dl))
    latch = modes([880, 1960, 3100], [0.12, 0.06, 0.03], [1, .6, .3], 0.3) * 0.35
    rise = modes([660, 990, 1320], [0.4, 0.3, 0.25], [1, .7, .5], 0.7) * 0.25   # positive shimmer
    x = mix(*parts, at(latch, 0.03), at(rise, 0.08))
    return fade_out(norm(reverb(x, 0.8, 0.2), 0.8))


def roar():
    d = 1.9; t = t_(d)
    pitch = 62 + 28 * np.sin(np.pi * np.clip(t / 1.4, 0, 1)) - 10 * (t / d)
    pitch *= 1 + 0.03 * np.sin(2 * np.pi * 7 * t) + 0.02 * nz(d) * 0
    ph = 2 * np.pi * np.cumsum(pitch) / SR
    src = signal.sawtooth(ph) + 0.6 * signal.sawtooth(ph * 0.5) + 0.8 * lp(nz(d), 3000)
    v = mix(bp(src, 300, 750) * 1.1, bp(src, 800, 1400) * 0.8, bp(src, 2000, 3200) * 0.35, lp(src, 220) * 0.9)
    e = np.clip(t / 0.18, 0, 1) * np.clip((d - t) / 0.6, 0, 1)
    x = sat(v * e * 2.2, 3.0)
    x = mix(x, lp(nz(d), 160) * e * 0.5)
    return fade_out(norm(reverb(x, 2.2, 0.35, 2500), 0.95))


def quake():
    d = 1.6
    sub = sweep_sine(55, 30, d, 0.5) * env_exp(d, 0.45, 0.004) * 1.0
    rumble = lp(nz(d), 220, 3) * env_exp(d, 0.5, 0.01) * 0.9
    crack = lp(nz(0.05), 2500) * env_exp(0.05, 0.01) * 0.8
    deb = mix(*[at(bp(nz(0.04), 900, 3500) * env_exp(0.04, 0.007) * (0.15 + rng.random() * 0.2), 0.12 + rng.random() * 0.7) for _ in range(14)])
    x = mix(sub, rumble, crack, deb)
    return fade_out(norm(reverb(sat(x * 1.4, 1.6), 1.6, 0.25, 1800), 0.95))


def slash():
    d = 0.75; t = t_(d)
    src = nz(d); out = np.zeros_like(src)
    # moving bandpass whoosh in blocks
    n = 24; L = len(src) // n
    for i in range(n):
        f = 300 * (14 ** (i / n)); seg = bp(src[i * L:(i + 2) * L], f * 0.7, min(f * 1.4, 15000))
        out[i * L:i * L + len(seg)] += seg * np.hanning(len(seg))
    e = np.sin(np.pi * np.clip(t / d, 0, 1)) ** 1.5
    zap = hp(nz(d), 5000) * (rng.random(len(t)) > 0.985) * 3.0
    hum = sweep_sine(180, 520, d, 1.2) * 0.25
    x = mix(out * e, zap * e * 0.5, hum * e)
    return fade_out(norm(reverb(x, 1.0, 0.25), 0.8))


def explosion():
    d = 3.2
    crack = hp(nz(0.03), 1200) * env_exp(0.03, 0.006) * 1.0
    boom = sweep_sine(70, 26, 1.5, 0.4) * env_exp(1.5, 0.45, 0.003) * 1.2
    body = lp(nz(d), 900, 3) * env_exp(d, 0.38, 0.004) * 1.1
    rumble = lp(nz(d), 140, 3) * env_exp(d, 1.0, 0.05) * 1.0
    deb = mix(*[at(bp(nz(0.06), 700, 4000) * env_exp(0.06, 0.012) * (0.1 + rng.random() * 0.25), 0.25 + rng.random() * 1.8) for _ in range(26)])
    x = mix(crack, boom, body, rumble, deb)
    return fade_out(norm(reverb(sat(x * 1.6, 2.2), 2.4, 0.3, 1600), 0.98), 0.3)


def glass():
    d = 1.1
    hit = hp(nz(0.04), 2500) * env_exp(0.04, 0.01) * 1.0
    shards = []
    for i in range(34):
        dl = rng.random() ** 1.6 * 0.8; f = 2500 + rng.random() * 6500
        shards.append(at(modes([f, f * 1.37, f * 2.11], [0.06, 0.04, 0.02], [1, .5, .3], 0.12) * (0.25 + rng.random() * 0.5), dl))
        shards.append(at(hp(nz(0.015), 4000) * env_exp(0.015, 0.003) * 0.4, dl))
    x = mix(hit, *shards)
    return fade_out(norm(reverb(x, 1.2, 0.25, 6000), 0.75))


def servo():
    d = 1.5; t = t_(d)
    f = 140 + 380 * np.clip(t / 1.0, 0, 1) ** 0.8; f *= 1 + 0.02 * np.sin(2 * np.pi * 23 * t)
    ph = 2 * np.pi * np.cumsum(f) / SR
    motor = bp(signal.sawtooth(ph) + 0.3 * signal.sawtooth(ph * 2.01), 200, 2500) * 0.5
    hiss = bp(nz(d), 2000, 7000) * np.clip(np.sin(np.pi * t / d), 0, 1) * 0.25
    clunks = mix(*[at(mix(lp(nz(0.06), 600) * env_exp(0.06, 0.012), modes([310, 720], [0.08, 0.05], [1, .5], 0.12) * 0.4), dl) for dl in (0.05, 0.62, 1.18)])
    x = mix(motor * np.clip(np.sin(np.pi * t / d), 0, 1), hiss, clunks * 1.2)
    return fade_out(norm(reverb(x, 0.9, 0.2), 0.85))


def hammer_slam():
    d = 1.2
    tr = lp(nz(0.02), 4000) * env_exp(0.02, 0.004) * 1.0
    thump = sweep_sine(95, 40, 0.35, 0.5) * env_exp(0.35, 0.09) * 1.2
    crunch = bp(nz(0.4), 300, 2200) * env_exp(0.4, 0.07, 0.003) * 0.6
    ring = modes([420, 1033, 1610, 2380], [0.35, 0.22, 0.14, 0.08], [1, .6, .4, .25], d) * 0.28
    deb = mix(*[at(bp(nz(0.04), 800, 3500) * env_exp(0.04, 0.007) * 0.2, 0.08 + rng.random() * 0.4) for _ in range(8)])
    x = mix(tr, thump, crunch, ring, deb)
    return fade_out(norm(reverb(sat(x * 1.3, 1.5), 1.1, 0.22), 0.92))


def impact():
    d = 1.0
    thump = sweep_sine(80, 35, 0.45, 0.5) * env_exp(0.45, 0.12) * 1.1
    body = lp(nz(d), 700) * env_exp(d, 0.14, 0.003) * 0.8
    deb = mix(*[at(bp(nz(0.04), 700, 3000) * env_exp(0.04, 0.007) * 0.18, 0.05 + rng.random() * 0.5) for _ in range(10)])
    x = mix(thump, body, deb)
    return fade_out(norm(reverb(x, 1.0, 0.2), 0.9))


def brass(notes, durs, gaps, final_hit=True):
    parts = []; tpos = 0
    for n_, dd, g in zip(notes, durs, gaps):
        t = t_(dd); voice = np.zeros_like(t)
        for det in (-0.004, 0, 0.005):
            f = n_ * (1 + det); ph = 2 * np.pi * f * t + 4 * np.sin(2 * np.pi * 5.2 * t) * 0.002
            voice += signal.sawtooth(ph)
        e = np.clip(t / 0.05, 0, 1) * np.clip((dd - t) / 0.12, 0, 1)
        bright = 600 + 2200 * np.clip(t / 0.08, 0, 1)
        v = lp(voice, 2600) * e * 0.35
        parts.append(at(v, tpos)); tpos += g
    x = mix(*parts)
    if final_hit:
        timp = sweep_sine(110, 70, 0.8, 0.5) * env_exp(0.8, 0.25, 0.002) * 0.9 + lp(nz(0.8), 300) * env_exp(0.8, 0.12) * 0.4
        x = mix(x, at(timp, max(0, tpos - gaps[-1])))
    return fade_out(norm(reverb(x, 1.8, 0.3, 4000), 0.8), 0.15)


def ui_click():
    x = mix(hp(nz(0.008), 1500) * env_exp(0.008, 0.0015), modes([1900, 3300], [0.012, 0.008], [1, .5], 0.04) * 0.5)
    return fade_out(norm(x, 0.35), 0.005)


def good_chime():
    x = mix(modes([880, 1760, 2640, 3520 * 1.01], [0.5, 0.35, 0.25, 0.18], [1, .5, .3, .2], 0.9) * 0.5,
            at(modes([1318.5, 2637, 3955], [0.5, 0.35, 0.2], [1, .45, .25], 0.9) * 0.45, 0.07),
            at(modes([1760, 3520, 5280], [0.6, 0.4, 0.2], [1, .4, .2], 1.0) * 0.4, 0.14))
    whoosh = bp(nz(0.4), 1500, 6000) * np.sin(np.pi * np.clip(t_(0.4) / 0.4, 0, 1)) * 0.12
    return fade_out(norm(reverb(mix(x, whoosh), 1.2, 0.25, 6000), 0.6))


def bad_thunk():
    d = 0.7; t = t_(d)
    tone_ = signal.sawtooth(2 * np.pi * np.cumsum(220 * (1 - 0.45 * t / d)) / SR) * env_exp(d, 0.25, 0.01)
    x = mix(lp(tone_, 900) * 0.6, lp(nz(0.12), 500) * env_exp(0.12, 0.03) * 0.8)
    return fade_out(norm(reverb(x, 0.8, 0.18), 0.6))


C4, E4, G4, C5, A3, F3, D4 = 261.6, 329.6, 392.0, 523.3, 220.0, 174.6, 293.7
SOUNDS = {
    'shot': [gunshot(k) for k in range(4)],
    'kill': [zombie_hit(k) for k in range(3)],
    'hurt': [grunt(k) for k in range(2)],
    'tick': [coin(k) for k in range(2)],
    'tink': [ping(k) for k in range(3)],
    'crate': [crate_break()],
    'roar': [roar()],
    'quake': [quake()],
    'slash': [slash()],
    'boom': [explosion()],
    'shatter': [glass()],
    'mech': [servo()],
    'slam': [hammer_slam()],
    'impact': [impact()],
    'good': [good_chime()],
    'bad': [bad_thunk()],
    'win': [brass([C4, E4, G4, C5], [0.5, 0.5, 0.5, 1.2], [0.14, 0.14, 0.14, 0.0])],
    'lose': [brass([G4 * 0.5 * 2, E4 * 0.5 * 2, D4 * 0.5 * 2, C4 * 0.5 * 2], [0.45, 0.45, 0.45, 1.3], [0.22, 0.22, 0.22, 0.0])],
    'click': [ui_click()],
}
def trim(x, thr=0.004, maxd=None):
    a = np.abs(x); e = signal.sosfilt(signal.butter(1, 30, 'lowpass', fs=SR, output='sos'), a)
    idx = np.nonzero(e > thr)[0]; end = (idx[-1] if len(idx) else len(x)) + int(SR * 0.03)
    if maxd: end = min(end, int(SR * maxd))
    return fade_out(x[:end], 0.03)
MAXD = {'shot': 0.5, 'kill': 0.6, 'hurt': 0.5, 'tink': 0.18, 'roar': 2.6, 'boom': 4.0, 'quake': 2.4, 'win': 2.8, 'lose': 3.0, 'good': 1.4, 'mech': 1.9, 'slam': 1.6, 'impact': 1.4, 'crate': 1.2, 'shatter': 1.6, 'slash': 1.1, 'bad': 1.0, 'tick': 0.4}
SOUNDS = {k: [trim(v, maxd=MAXD.get(k)) for v in vs] for k, vs in SOUNDS.items()}
meta = {}
from scipy.io import wavfile
for name, vs in SOUNDS.items():
    meta[name] = []
    for i, v in enumerate(vs):
        w = os.path.join(OUT, '%s_%d.wav' % (name, i)); m = os.path.join(OUT, '%s_%d.mp3' % (name, i))
        wavfile.write(w, SR, (np.clip(v, -1, 1) * 32767).astype(np.int16))
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', w, '-ac', '1', '-ar', '32000', '-b:a', '48k', m], check=True)
        meta[name].append(os.path.basename(m))
tot = sum(os.path.getsize(os.path.join(OUT, f)) for v in meta.values() for f in v)
json.dump(meta, open(os.path.join(OUT, 'sfx.json'), 'w'))
print('sounds', len(meta), 'files', sum(len(v) for v in meta.values()), 'mp3 total KB', tot // 1024)
