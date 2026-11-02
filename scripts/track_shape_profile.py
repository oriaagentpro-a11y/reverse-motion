"""Décalque of large soft shapes (ground, band, wave) and of a round element (ball, bubble).

Usage: python3 track_shape_profile.py <video> <start_s> <end_s> <out.json>
        --shape-color 80,0,176 [--shape-tol 70] [--open 31] [--step 4]
        [--ball-hsv smin,smax,vmin] [--ball-min-area 600]
For each frame:
- shape: pixels close to --shape-color, then a morphological opening with an --open x --open
  kernel removes thin things (text, outlines) so only the thick shape remains; for every column
  (every --step px) the first run from the top gives [top, bottom] of the shape (null if absent).
- ball (optional): pixels inside the HSV saturation band and above the value threshold, holes
  filled, the most circular large component -> centre and radius (minimum enclosing circle).
The scene redraws the shape as a polygon from these profiles and places the ball each frame.
"""
import sys, json
import numpy as np
import cv2


def arg(a, k, d):
    return a[a.index(k) + 1] if k in a else d


def main():
    a = sys.argv
    video, t0, t1, out = a[1], float(a[2]), float(a[3]), a[4]
    col = np.array([int(v) for v in arg(a, '--shape-color', '80,0,176').split(',')][::-1], float)
    tol = float(arg(a, '--shape-tol', 70)); k = int(arg(a, '--open', 31)); step = int(arg(a, '--step', 4))
    ball = arg(a, '--ball-hsv', None); min_area = int(arg(a, '--ball-min-area', 600))
    cap = cv2.VideoCapture(video); fps = cap.get(cv2.CAP_PROP_FPS)
    f0, f1 = round(t0 * fps), round(t1 * fps); cap.set(cv2.CAP_PROP_POS_FRAMES, f0)
    VW = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)); xs = list(range(0, VW, step)) + [VW - 1]
    rows = {}
    for f in range(f0, f1):
        ok, img = cap.read()
        if not ok:
            break
        m = (np.linalg.norm(img.astype(float) - col, axis=2) < tol).astype(np.uint8)
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
        prof = []
        for x in xs:
            c = m[:, x]; ys = np.where(c)[0]
            if len(ys) == 0:
                prof.append(None); continue
            top = int(ys[0]); gaps = np.where(np.diff(ys) > 1)[0]
            bot = int(ys[gaps[0]]) if len(gaps) else int(ys[-1])
            prof.append([top, bot])
        row = {'profile': prof}
        if ball:
            smin, smax, vmin = map(int, ball.split(','))
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            b = ((hsv[:, :, 1] >= smin) & (hsv[:, :, 1] <= smax) & (hsv[:, :, 2] >= vmin)).astype(np.uint8)
            b = cv2.morphologyEx(b, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
            # Hough on the filled mask: robust when the ball touches another shape of similar colour
            cnts, _ = cv2.findContours(b, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            filled = np.zeros_like(b); cv2.drawContours(filled, [c for c in cnts if cv2.contourArea(c) >= min_area], -1, 255, -1)
            circles = cv2.HoughCircles(cv2.GaussianBlur(filled, (0, 0), 2), cv2.HOUGH_GRADIENT, dp=1, minDist=60,
                                       param1=120, param2=18, minRadius=12, maxRadius=160)
            if circles is not None:
                best = None
                for cx, cy, r in circles[0]:
                    yy, xx = np.ogrid[:b.shape[0], :b.shape[1]]
                    disk = (xx - cx) ** 2 + (yy - cy) ** 2 <= r * r
                    fill = filled[disk].mean() / 255 if disk.any() else 0
                    if fill > 0.8 and (best is None or r * fill > best[2] * best[3]):
                        best = (float(cx), float(cy), float(r), float(fill))
                if best:
                    row['ball'] = [round(best[0], 2), round(best[1], 2), round(best[2], 2), round(best[3], 3)]
        rows[f] = row
    json.dump({'xs': xs, 'frames': rows}, open(out, 'w'))
    nb = sum('ball' in r for r in rows.values())
    print(f'{len(rows)} frames, ball found in {nb} -> {out}')


if __name__ == '__main__':
    main()
