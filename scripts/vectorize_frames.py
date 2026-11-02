"""Rotoscopie vectorielle : trace, image par image, le contour d'une couleur de la vidéo en chemins SVG.

Usage: python3 vectorize_frames.py <video> <start_s> <end_s> <out.js>
        --color 80,0,176 [--tol 110] [--exclude x,y,w,h ...] [--up 4] [--eps 0.35] [--min-area 4]
        [--var NAME]

When to use it: a shape whose geometry cannot be re-simulated exactly (stylised map on a globe,
hand-drawn splash, liquid blob...). The traced paths keep the shape editable (colour, stroke,
timing) and match the source trait pour trait.

How: the colour distance gives a soft alpha (anti-aliasing kept); the alpha is upsampled --up
times (bicubic) and cut at 0.5, so contours land on sub-pixel positions; contours with holes
(RETR_CCOMP) are simplified by --eps source pixels and written as one evenodd path per frame.
Output: a JS file `window.<NAME> = { "<frame>": "M... Z M... Z", ... }` (scenes load it with
<script>, which also works over file://).
"""
import sys, json
import numpy as np
import cv2


def arg(a, k, d):
    return a[a.index(k) + 1] if k in a else d


def main():
    a = sys.argv
    video, t0, t1, out = a[1], float(a[2]), float(a[3]), a[4]
    col = np.array([int(v) for v in arg(a, '--color', '80,0,176').split(',')][::-1], float)
    tol = float(arg(a, '--tol', 110)); up = int(arg(a, '--up', 4)); eps = float(arg(a, '--eps', 0.35))
    min_area = float(arg(a, '--min-area', 4)); name = arg(a, '--var', 'ROTO')
    excl = []
    if '--exclude' in a:
        i = a.index('--exclude') + 1
        while i < len(a) and not a[i].startswith('--'):
            excl.append([int(v) for v in a[i].split(',')]); i += 1
    cap = cv2.VideoCapture(video); fps = cap.get(cv2.CAP_PROP_FPS)
    f0, f1 = round(t0 * fps), round(t1 * fps); cap.set(cv2.CAP_PROP_POS_FRAMES, f0)
    frames = {}
    for f in range(f0, f1):
        ok, img = cap.read()
        if not ok:
            break
        d = np.linalg.norm(img.astype(float) - col, axis=2)
        alpha = np.clip(1 - d / tol, 0, 1).astype(np.float32)          # soft coverage of the colour
        for x, y, w, h in excl:
            alpha[y:y + h, x:x + w] = 0
        big = cv2.resize(alpha, None, fx=up, fy=up, interpolation=cv2.INTER_CUBIC)
        m = (big > 0.5).astype(np.uint8)
        cnts, hier = cv2.findContours(m, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
        parts = []
        for c in cnts:
            if cv2.contourArea(c) < min_area * up * up:
                continue
            c = cv2.approxPolyDP(c, eps * up, True)
            if len(c) < 3:
                continue
            pts = (c[:, 0, :].astype(float) + 0.5) / up - 0.5 / up
            parts.append('M' + 'L'.join(f'{x:.2f} {y:.2f}' for x, y in pts) + 'Z')
        frames[f] = ''.join(parts)
    with open(out, 'w') as fh:
        fh.write(f'window.{name} = ' + json.dumps(frames) + ';')
    print(f'{len(frames)} frames traced -> {out} ({sum(len(v) for v in frames.values()) // 1024} KB of paths)')


if __name__ == '__main__':
    main()
