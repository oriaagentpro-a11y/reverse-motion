"""Recolour a video clip with a brand palette (used for extracted segments of a rebranded version).

Usage: python3 recolor.py <in.mp4> <out.mp4> <brand.js | brand.json> [--sigma 38]
The palette is BRAND.colors {'#source': '#brand', ...}. Every pixel gets soft weights towards each source
colour (Gaussian on the RGB distance); its colour is moved by the weighted difference (brand - source).
Anti-aliased edges and gradients between two palette colours are therefore remapped smoothly, and pixels far
from every palette colour (photos, other hues) stay untouched. Timing is never changed: frame n in = frame n out.
"""
import sys, os, re, json, subprocess
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rmcommon  # noqa: E402


def load_palette(path):
    txt = open(path, encoding='utf-8').read()
    if path.endswith('.json'):
        cols = json.loads(txt).get('colors', {})
    else:  # brand.js: read the colors object literal
        m = re.search(r'colors\s*:\s*\{([^}]*)\}', txt)
        cols = dict(re.findall(r"""['"](#[0-9A-Fa-f]{3,6})['"]\s*:\s*['"](#[0-9A-Fa-f]{3,6})['"]""", m.group(1))) if m else {}
    hx = lambda c: [int((c[1:] if len(c) == 7 else ''.join(x * 2 for x in c[1:]))[i:i + 2], 16) for i in (0, 2, 4)]
    return np.array([hx(k) for k in cols], np.float32), np.array([hx(v) for v in cols.values()], np.float32)


def recolor(img_rgb, src, dst, sigma):
    px = img_rgb.reshape(-1, 3).astype(np.float32)
    d2 = ((px[:, None, :] - src[None]) ** 2).sum(2)                      # (N, K)
    w = np.exp(-d2 / (2 * sigma * sigma))
    # between two palette colours (anti-aliasing): project on the segment so the edge keeps its exact mix
    out = px + w @ (dst - src) / np.maximum(1.0, w.sum(1, keepdims=True))
    K = len(src)
    for i in range(K):
        for j in range(i + 1, K):
            a, b = src[i], src[j]; ab = b - a; L2 = float(ab @ ab)
            if L2 < 1:
                continue
            t = np.clip(((px - a) @ ab) / L2, 0, 1)
            near = np.linalg.norm(px - (a + t[:, None] * ab), axis=1) < sigma * 0.6
            sel = near & (t > 0.04) & (t < 0.96)
            out[sel] = dst[i] + t[sel, None] * (dst[j] - dst[i])
    return np.clip(out + 0.5, 0, 255).astype(np.uint8).reshape(img_rgb.shape)


def main():
    a = sys.argv
    src_v, out_v, brand = a[1], a[2], a[3]
    sigma = rmcommon.arg(a, 'sigma', 38.0, float)
    src, dst = load_palette(brand)
    if not len(src):
        sys.exit('aucune couleur dans ' + brand)
    V = rmcommon.probe(src_v); W, H = V['w'], V['h']
    dec = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', src_v, '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], stdout=subprocess.PIPE)
    enc = subprocess.Popen(['ffmpeg', '-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', f"{V['fps']:g}",
                            '-i', '-', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '10', '-pix_fmt', 'yuv420p', out_v], stdin=subprocess.PIPE)
    n = 0
    while True:
        buf = dec.stdout.read(W * H * 3)
        if len(buf) < W * H * 3:
            break
        enc.stdin.write(recolor(np.frombuffer(buf, np.uint8).reshape(H, W, 3), src, dst, sigma).tobytes()); n += 1
    enc.stdin.close(); enc.wait(); dec.wait()
    print(f'{n} images recolorées -> {out_v}')


if __name__ == '__main__':
    main()
