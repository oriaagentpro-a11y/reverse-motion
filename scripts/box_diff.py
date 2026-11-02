"""Compare element boxes between original and copy at given frames.

Usage: python3 box_diff.py <original.mp4> <copy.mp4> <copy_offset_s> <frame> [<frame> ...] [--dark] [--thr T]
For each frame (index in the original), prints the components found in both videos
side by side, with the x / y / width / height error of the copy. Used by the correction loop
to turn a visual difference into a number to fix (offset, scale, font size).
"""
import sys
import numpy as np
import cv2


def comps(img, dark, thr):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    m = (g < 255 - thr) if dark else (g > thr)
    m = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((3, 9), np.uint8))
    n, lab, st, cen = cv2.connectedComponentsWithStats(m)
    out = [tuple(int(v) for v in st[i][:4]) for i in range(1, n) if st[i][4] >= 20]
    return sorted(out)


def grab(path, frame):
    cap = cv2.VideoCapture(path); cap.set(cv2.CAP_PROP_POS_FRAMES, frame)
    ok, img = cap.read(); return img


def main():
    argv = [a for a in sys.argv[1:]]
    dark = '--dark' in argv
    thr = int(argv[argv.index('--thr') + 1]) if '--thr' in argv else 150
    pos = [a for i, a in enumerate(argv) if not a.startswith('--') and (i == 0 or argv[i - 1] != '--thr')]
    orig, copy, offset = pos[0], pos[1], float(pos[2])
    for f in map(int, pos[3:]):
        a = comps(grab(orig, f), dark, thr)
        b = comps(grab(copy, f - round(offset * (cv2.VideoCapture(orig).get(cv2.CAP_PROP_FPS) or 30))), dark, thr)
        print(f'frame {f}:')
        for i in range(max(len(a), len(b))):
            ca = a[i] if i < len(a) else None; cb = b[i] if i < len(b) else None
            err = tuple(np.subtract(cb, ca)) if ca and cb else None
            print(f'  orig {ca}  copy {cb}  err(x,y,w,h) {err}')


if __name__ == '__main__':
    main()
