"""Measure the ink box of a text on every frame (decalque of size + position, no limit on motion).

Usage: python3 track_textbox.py <video> <f0> <f1> <x,y,w,h roi> <ink_hex> <tol> <out.json> [--key name] [--min-area 30]
Pixels within `tol` of the ink colour inside the ROI are grouped; the union box of the significant
components gives [left, top, width, height] for the frame (missing when nothing is found).
The scene replays it with RM.fitInk(el, {left, top, w}) at every frame.
The result is merged into out.json under `key` (so one file can hold several texts).
"""
import sys, os, json
import numpy as np
import cv2


def main():
    a = sys.argv
    video, f0, f1 = a[1], int(a[2]), int(a[3])
    x, y, w, h = map(int, a[4].split(',')); col = a[5]; tol = float(a[6]); out = a[7]
    key = a[a.index('--key') + 1] if '--key' in a else 'text'
    min_area = int(a[a.index('--min-area') + 1]) if '--min-area' in a else 30
    C = np.array([int(col[i:i + 2], 16) for i in (4, 2, 0)], np.float32)
    cap = cv2.VideoCapture(video); cap.set(cv2.CAP_PROP_POS_FRAMES, f0)
    rows = {}
    for f in range(f0, f1 + 1):
        ok, im = cap.read()
        if not ok:
            break
        m = (np.linalg.norm(im[y:y + h, x:x + w].astype(np.float32) - C, axis=2) < tol).astype(np.uint8)
        n, lab, st, _ = cv2.connectedComponentsWithStats(m)
        comps = [s for s in st[1:] if s[4] >= min_area]
        if not comps:
            continue
        x0 = min(c[0] for c in comps); y0 = min(c[1] for c in comps)
        x1 = max(c[0] + c[2] for c in comps); y1 = max(c[1] + c[3] for c in comps)
        rows[f] = [int(x + x0), int(y + y0), int(x1 - x0), int(y1 - y0)]
    data = json.load(open(out)) if os.path.exists(out) else {}
    data[key] = rows
    json.dump(data, open(out, 'w'))
    print(f'{key}: {len(rows)} frames -> {out}')


if __name__ == '__main__':
    main()
