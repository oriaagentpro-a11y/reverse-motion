"""Text pose per frame: font size and rotation of each tracked word, from its ink box and its ink.

Usage: python3 fit_text_pose.py <video> <word_tracks.json> <font.ttf> [--weights 400:a.ttf,500:b.ttf]
A tilted word has an axis-aligned ink box that is TALLER and relatively narrower than the upright word:
fitting the font by the box height then gives letters that are too big (seen on 3D-camera videos).
For each tracked frame, with the word's natural ink size (a, b) at size 100 (same font file):
    W = k (a cos t + b sin t),  H = k (a sin t + b cos t)
is solved for the scale k and the tilt t (0..40 deg); the sign of t comes from the orientation of the ink
(second-order moments). Adds to each word: "pose": {frame: [cx, cy, font_size, angle_deg]} (centre of the box).
The scene draws the word at that size, centred, rotated by angle (RM.fitInk with cx/cy + rotate).
"""
import sys, os, json, math
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rmcommon  # noqa: E402


def natural(text, font_path, weight=None):
    f = ImageFont.truetype(font_path, 100)
    if weight:
        try:
            f.set_variation_by_axes([weight])          # variable font: same weight as the scene
        except Exception:
            pass
    im = Image.new('L', (110 * len(text) + 100, 300)); ImageDraw.Draw(im).text((30, 60), text, font=f, fill=255)
    a = np.array(im) > 100; ys, xs = np.where(a)
    return xs.max() - xs.min() + 1, ys.max() - ys.min() + 1


def solve(W, H, a, b):
    R, R0 = W / H, a / b
    if R >= R0 * 0.985:
        return W / a, 0.0                       # upright (the box is only wider: glow, keep the width)
    best = None
    for t in np.linspace(0, math.radians(40), 401):
        r = (a * math.cos(t) + b * math.sin(t)) / (a * math.sin(t) + b * math.cos(t))
        if best is None or abs(r - R) < best[0]:
            best = (abs(r - R), t)
    t = best[1]
    return W / (a * math.cos(t) + b * math.sin(t)), math.degrees(t)


def main():
    a = sys.argv
    video, wt, font = a[1], a[2], a[3]
    fonts = {}
    for kv in (rmcommon.arg(a, 'weights', '') or '').split(','):
        if ':' in kv:
            w, p = kv.split(':', 1); fonts[int(w)] = p
    W_ = json.load(open(wt))
    cap = cv2.VideoCapture(video); FR = []
    while True:
        ok, im = cap.read()
        if not ok:
            break
        FR.append(im.max(2))   # one channel uint8 per frame (memory)
    for k, v in W_.items():
        fp = fonts.get(v.get('weight') or 0, font)
        na, nb = natural(v['text'], fp, v.get('weight')) if v['text'] else (1, 1)
        pose = {}
        for f, bx in v['track'].items():
            x, y, w, h = bx[:4]
            s, ang = solve(w, h, na, nb)
            if ang > 1.0:      # sign of the tilt: orientation of the ink inside the box
                c = FR[int(f)][max(0, int(y)):int(y + h), max(0, int(x)):int(x + w)].astype(np.float32)
                if c.size:
                    m = (c > np.percentile(c, 70)).astype(np.uint8)
                    M = cv2.moments(m)
                    if M['m00'] > 0:
                        th = 0.5 * math.atan2(2 * M['mu11'], M['mu20'] - M['mu02'])   # image axes: y down
                        ang = ang if th > 0 else -ang
            pose[f] = [round(x + w / 2, 2), round(y + h / 2, 2), round(s * 100, 3), round(ang, 2)]
        v['pose'] = pose; v['natural100'] = [int(na), int(nb)]
        r = pose.get(str(v['ref']))
        print(f"{k:14s} {v['text']:9s} ref : taille {r[2]:6.1f}  angle {r[3]:6.1f}°" if r else k)
    json.dump(W_, open(wt, 'w'))


if __name__ == '__main__':
    main()
