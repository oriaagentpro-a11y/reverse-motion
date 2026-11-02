"""Generate the demo "original" video (64 s, 640x360, 25 fps, with music) — free of any third-party rights.

Usage: python3 make_source.py [out.mp4]   (default: src/source.mp4 next to this file)
It is drawn with Pillow (another rasteriser than the browser), so the reproduction is a real test:
the copy must find positions, sizes, easings and timings from the video, not from this file.
"""
import sys, os, math, subprocess, tempfile
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONT = os.path.join(HERE, '..', '..', 'engine', 'Outfit-var.ttf')
W, H, FPS, DUR, SS = 640, 360, 25, 64.0, 2
CREAM, TEAL, WARM, INK = (255, 247, 237), (15, 118, 110), (245, 158, 11), (31, 41, 55)
WORDS = ['Créer', 'Mesurer', 'Copier', 'Livrer']

p2io = lambda p: 2 * p * p if p < .5 else 1 - (-2 * p + 2) ** 2 / 2
p2in = lambda p: p * p
p1out = lambda p: 1 - (1 - p) ** 2
def backout(p, s=1.70158): p -= 1; return 1 + (s + 1) * p ** 3 + s * p ** 2
clamp = lambda v, a=0., b=1.: max(a, min(b, v))
mix = lambda a, b, k: tuple(round(x + (y - x) * k) for x, y in zip(a, b))
_fonts = {}


def font(size, wt):
    k = (round(size * SS), wt)
    if k not in _fonts:
        f = ImageFont.truetype(FONT, k[0]); f.set_variation_by_axes([wt]); _fonts[k] = f
    return _fonts[k]


def text(d, s, cx, cy, size, wt, fill):  # centred on its ink box
    f = font(size, wt); x0, y0, x1, y1 = d.textbbox((0, 0), s, font=f)
    d.text((cx * SS - (x0 + x1) / 2, cy * SS - (y0 + y1) / 2), s, font=f, fill=fill)


def frame(t):
    im = Image.new('RGB', (W * SS, H * SS), CREAM); d = ImageDraw.Draw(im)
    S = lambda *v: [x * SS for x in v]
    if t < 16:  # S1: a ball travelling back and forth, title fading in
        k = clamp((t - 1.0) / 0.4); text(d, 'Bouge.', 320, 80, 54, 700, mix(CREAM, TEAL, k))
        n = int(max(0, t - 0.5) // 2); p = clamp((t - 0.5 - 2 * n) / 1.2); e = p2io(p)
        x = 80 + (560 - 80) * (e if n % 2 == 0 else 1 - e)
        if t < 0.5: x = 80
        d.ellipse(S(x - 28, 180 - 28, x + 28, 180 + 28), fill=TEAL)
    elif t < 32:  # S2: one word per beat (0.5 s), popping in
        d.rectangle([0, 0, W * SS, H * SS], fill=INK)
        i = int((t - 16) // 0.5); p = clamp(((t - 16) - 0.5 * i) / 0.25)
        text(d, WORDS[i % 4], 320, 180, 64 * (0.6 + 0.4 * backout(p)), 800, WARM)
    elif t < 48:  # S3: rotating square + progress bar
        a = math.radians(90 * (t - 32)); c, s = math.cos(a), math.sin(a)
        pts = [(320 + 45 * (c * x - s * y), 160 + 45 * (s * x + c * y)) for x, y in [(-1, -1), (1, -1), (1, 1), (-1, 1)]]
        d.polygon([(x * SS, y * SS) for x, y in pts], fill=TEAL)
        d.rounded_rectangle(S(60, 294, 580, 306), radius=6 * SS, fill=(237, 226, 210))
        wbar = 520 * (t - 32) / 16
        if wbar > 12: d.rounded_rectangle(S(60, 294, 60 + wbar, 306), radius=6 * SS, fill=WARM)
    else:  # S4: circle wipe, counter, end card
        r = 760 * p2in(clamp((t - 48.2) / 0.8))
        if r > 0: d.ellipse(S(320 - r, 180 - r, 320 + r, 180 + r), fill=WARM)
        if t >= 49.5:
            v = round(100 * p1out(clamp((t - 49.5) / 3.0)))
            text(d, str(v), 320, 165, 96, 800, INK); text(d, '% fidèle', 320, 245, 30, 400, INK)
        k = clamp((t - 60) / 0.5)
        if k > 0:
            ov = Image.new('RGB', im.size, TEAL); dv = ImageDraw.Draw(ov); text(dv, 'Fin.', 320, 180, 80, 700, CREAM)
            im = Image.blend(im, ov, k)
    return im.resize((W, H), Image.LANCZOS)


def music(path, sr=44100):  # 120 BPM: kick on every beat, accent on bar starts, soft pad
    n = int(DUR * sr); y = np.zeros(n)
    tt = np.arange(int(0.18 * sr)) / sr
    kick = np.sin(2 * np.pi * (55 + 90 * np.exp(-tt * 30)) * tt) * np.exp(-tt * 18)
    for b in range(int(DUR * 2)):
        i = int(b * 0.5 * sr); g = 1.0 if b % 4 == 0 else 0.55
        y[i:i + len(kick)] += g * kick[:max(0, min(len(kick), n - i))]
    ta = np.arange(n) / sr; y += 0.06 * np.sin(2 * np.pi * 220 * ta) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.125 * ta))
    pcm = (np.clip(y / np.abs(y).max(), -1, 1) * 30000).astype('<i2')
    import wave
    with wave.open(path, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(pcm.tobytes())


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'src', 'source.mp4')
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        wav = os.path.join(td, 'm.wav'); music(wav)
        enc = subprocess.Popen(['ffmpeg', '-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS),
                                '-i', '-', '-i', wav, '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '14', '-pix_fmt', 'yuv420p',
                                '-c:a', 'aac', '-shortest', out], stdin=subprocess.PIPE)
        for f in range(int(DUR * FPS)):
            enc.stdin.write(frame(f / FPS).tobytes())
        enc.stdin.close(); enc.wait()
    print('->', out)


if __name__ == '__main__':
    main()
