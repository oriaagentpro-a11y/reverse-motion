"""Measure the 4 corners of a flat card (white pill, panel, button) on every frame.

Usage: python3 track_quad.py <video> <start_s> <end_s> <out.json> [--color FFFFFF] [--tol 60]
       [--roi x,y,w,h] [--min-area 400] [--pick largest|nearest:x,y] [--soft]
A pixel belongs to the card when its colour is within `tol` of `color`. The biggest blob (or the one
nearest a point) is kept; its contour is reduced to 4 corners (minAreaRect when the shape is a
rotated rectangle, else the convex-hull quadrilateral, which captures perspective).
--soft  : motion-blurred edges -> the corners are taken on the 50 % iso-line of a blurred mask.
Output: {"rows": {frame: {"quad": [[x,y] x4, clockwise from top-left], "center": [x,y],
                          "angle": deg, "size": [w,h], "area": n}}}
The scene maps its element onto the quad (CSS matrix3d / SVG matrix), so position, rotation,
scale and perspective follow the original image for image.
"""
import sys, json
import numpy as np
import cv2


def order(pts):
    pts = np.array(pts, np.float32)
    c = pts.mean(0)
    ang = np.arctan2(pts[:, 1] - c[1], pts[:, 0] - c[0])
    pts = pts[np.argsort(ang)]                       # clockwise in image coords, starting at top-left
    i = np.argmin(pts[:, 0] + pts[:, 1])
    return np.roll(pts, -i, 0)


def quad_of(cnt):
    hull = cv2.convexHull(cnt)
    peri = cv2.arcLength(hull, True)
    for eps in np.linspace(0.01, 0.12, 23):
        ap = cv2.approxPolyDP(hull, eps * peri, True)
        if len(ap) == 4:
            return order(ap[:, 0, :])
    r = cv2.minAreaRect(cnt)
    return order(cv2.boxPoints(r))


def main():
    a = sys.argv
    video, t0, t1, out = a[1], float(a[2]), float(a[3]), a[4]
    opt = lambda k, d: a[a.index(k) + 1] if k in a else d
    col = opt('--color', 'FFFFFF').lstrip('#'); C = np.array([int(col[i:i + 2], 16) for i in (4, 2, 0)], np.float32)
    tol = float(opt('--tol', 60)); min_area = int(opt('--min-area', 400)); soft = '--soft' in a
    roi = list(map(int, opt('--roi', '0,0,10000,10000').split(',')))
    pick = opt('--pick', 'largest')
    cap = cv2.VideoCapture(video); fps = cap.get(cv2.CAP_PROP_FPS)
    cap.set(cv2.CAP_PROP_POS_FRAMES, round(t0 * fps))
    rows = {}
    for f in range(round(t0 * fps), round(t1 * fps)):
        ok, img = cap.read()
        if not ok:
            break
        d = np.linalg.norm(img.astype(np.float32) - C, axis=2)
        if soft:
            m = (cv2.GaussianBlur(np.clip(1 - d / (2 * tol), 0, 1), (0, 0), 1.5) > 0.5)
        else:
            m = d < tol
        m = m.astype(np.uint8)
        x, y, w, h = roi; keep = np.zeros_like(m); keep[y:y + h, x:x + w] = 1; m &= keep
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))   # bridge the text holes
        cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        cnts = [c for c in cnts if cv2.contourArea(c) >= min_area]
        if not cnts:
            continue
        if pick.startswith('nearest'):
            px, py = map(float, pick.split(':')[1].split(','))
            c = min(cnts, key=lambda c: np.hypot(*(c[:, 0, :].mean(0) - [px, py])))
        else:
            c = max(cnts, key=cv2.contourArea)
        q = quad_of(c)
        r = cv2.minAreaRect(c)
        rows[f] = {'quad': np.round(q, 2).tolist(), 'center': np.round(q.mean(0), 2).tolist(),
                   'angle': round(float(np.degrees(np.arctan2(q[1][1] - q[0][1], q[1][0] - q[0][0]))), 3),
                   'size': [round(float(np.linalg.norm(q[1] - q[0])), 2), round(float(np.linalg.norm(q[3] - q[0])), 2)],
                   'area': int(cv2.contourArea(c))}
    json.dump({'rows': rows}, open(out, 'w'))
    print(f'{len(rows)} frames with a quad -> {out}')


if __name__ == '__main__':
    main()
