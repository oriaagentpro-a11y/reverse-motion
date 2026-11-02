"""Track bright (or dark) elements over a frame range.

Usage: python3 track_elements.py <video> <start_s> <end_s> <out.json> [--dark] [--min-area N] [--thr T]
For every frame, pixels whose luminance stands out from the background are grouped into
components; each component's box, centre, area and mean luminance are recorded.
The output feeds the easing fitter.
"""
import sys, json
import numpy as np
import cv2


def main():
    video, t0, t1, out = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4]
    dark = '--dark' in sys.argv
    min_area = int(sys.argv[sys.argv.index('--min-area') + 1]) if '--min-area' in sys.argv else 6
    thr = int(sys.argv[sys.argv.index('--thr') + 1]) if '--thr' in sys.argv else 150
    cap = cv2.VideoCapture(video)
    fps = cap.get(cv2.CAP_PROP_FPS)
    f0, f1 = round(t0 * fps), round(t1 * fps)
    cap.set(cv2.CAP_PROP_POS_FRAMES, f0)
    rows = []
    for f in range(f0, f1):
        ok, img = cap.read()
        if not ok:
            break
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        m = (g < 255 - thr) if dark else (g > thr)
        m = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((3, 9), np.uint8))
        n, lab, st, cen = cv2.connectedComponentsWithStats(m)
        comps = []
        for i in range(1, n):
            x, y, w, h, a = st[i]
            if a < min_area:
                continue
            comps.append({'x': int(x), 'y': int(y), 'w': int(w), 'h': int(h), 'area': int(a),
                          'cx': round(float(cen[i][0]), 2), 'cy': round(float(cen[i][1]), 2),
                          'lum': round(float(g[lab == i].mean()), 1)})
        comps.sort(key=lambda c: c['x'])
        if comps:
            xs = [c['x'] for c in comps]; ys = [c['y'] for c in comps]
            xe = [c['x'] + c['w'] for c in comps]; ye = [c['y'] + c['h'] for c in comps]
            union = {'x': min(xs), 'y': min(ys), 'w': max(xe) - min(xs), 'h': max(ye) - min(ys)}
        else:
            union = None
        rows.append({'frame': f, 't': round(f / fps, 4), 'union': union, 'components': comps})
    json.dump({'fps': fps, 'rows': rows}, open(out, 'w'))
    print(f'{len(rows)} frames tracked -> {out}')


if __name__ == '__main__':
    main()
