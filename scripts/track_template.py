"""Follow a small element (cursor, icon...) through the video by template matching.

Usage: python3 track_template.py <video> <template_frame_s> <x> <y> <w> <h> <start_s> <end_s> <out.json> [--scales 0.6,1.6] [--min-score 0.6]
The template is cut from the given frame; each frame is searched at several scales.
Output per frame: top-left x, y, scale and match score (frames under min-score are marked missing).
"""
import sys, json
import numpy as np
import cv2


def main():
    a = sys.argv
    video, tt = a[1], float(a[2])
    x, y, w, h = map(int, a[3:7])
    t0, t1, out = float(a[7]), float(a[8]), a[9]
    lo, hi = map(float, a[a.index('--scales') + 1].split(',')) if '--scales' in a else (0.7, 1.4)
    min_score = float(a[a.index('--min-score') + 1]) if '--min-score' in a else 0.6
    cap = cv2.VideoCapture(video); fps = cap.get(cv2.CAP_PROP_FPS)
    cap.set(cv2.CAP_PROP_POS_FRAMES, round(tt * fps)); ok, ref = cap.read()
    tpl = cv2.cvtColor(ref[y:y + h, x:x + w], cv2.COLOR_BGR2GRAY)
    scales = np.linspace(lo, hi, 15)
    rows = []
    cap.set(cv2.CAP_PROP_POS_FRAMES, round(t0 * fps))
    for f in range(round(t0 * fps), round(t1 * fps)):
        ok, img = cap.read()
        if not ok:
            break
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        best = (-1, None, None)
        for s in scales:
            t = cv2.resize(tpl, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
            if t.shape[0] >= g.shape[0] or t.shape[1] >= g.shape[1] or min(t.shape) < 4:
                continue
            r = cv2.matchTemplate(g, t, cv2.TM_CCOEFF_NORMED)
            _, mv, _, ml = cv2.minMaxLoc(r)
            if mv > best[0]:
                best = (mv, ml, s)
        sc, loc, s = best
        rows.append({'frame': f, 't': round(f / fps, 4), 'score': round(float(sc), 3),
                     'x': int(loc[0]) if sc >= min_score else None, 'y': int(loc[1]) if sc >= min_score else None,
                     'scale': round(float(s), 3) if sc >= min_score else None})
    json.dump({'template': [x, y, w, h], 'rows': rows}, open(out, 'w'))
    found = sum(r['x'] is not None for r in rows)
    print(f'{found}/{len(rows)} frames matched -> {out}')


if __name__ == '__main__':
    main()
