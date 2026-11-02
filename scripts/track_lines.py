"""Perspective tracking of text lines: a homography per frame, from the reference frame (ECC alignment).

Usage: python3 track_lines.py <video> <word_tracks.json> <out.json> [--min-cc 0.8] [--scale 0.5]
word_tracks.json = output of track_words.py (each word has "ref" and "ink_ref"). Words sharing the same
reference frame and the same row (vertical overlap) form a line. For each line, the region around its ink
on the reference frame is aligned on every other frame with cv2.findTransformECC (MOTION_HOMOGRAPHY),
starting from the previous frame's answer and going forward then backward until the correlation drops
under --min-cc. Text that is tilted, skewed or turning in 3D (a perspective camera move) is then
reproduced exactly: the scene draws the line as on the reference frame and applies the homography
(CSS matrix3d, RM.homographyMatrix3d).
Output: {line_id: {"words": [ids], "ref": f, "roi": [x, y, w, h], "H": {frame: [9 values, row-major], ...},
                   "cc": {frame: corr}}}
"""
import sys, os, json
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rmcommon  # noqa: E402


def lines_of(W):
    groups = []
    for k, v in sorted(W.items(), key=lambda kv: (kv[1]['ref'], kv[1]['ink_ref'][1])):
        x, y, w, h = v['ink_ref']
        for g in groups:
            if g['ref'] == v['ref'] and min(g['y1'], y + h) - max(g['y0'], y) > 0.35 * min(h, g['y1'] - g['y0']):
                g['words'].append(k); g['x0'] = min(g['x0'], x); g['x1'] = max(g['x1'], x + w)
                g['y0'] = min(g['y0'], y); g['y1'] = max(g['y1'], y + h); break
        else:
            groups.append({'ref': v['ref'], 'words': [k], 'x0': x, 'x1': x + w, 'y0': y, 'y1': y + h})
    return groups


def main():
    a = sys.argv
    video, wt, out = a[1], a[2], a[3]
    min_cc = rmcommon.arg(a, 'min-cc', 0.8, float); S = rmcommon.arg(a, 'scale', 0.5, float)
    W = json.load(open(wt))
    cap = cv2.VideoCapture(video); G = []
    while True:
        ok, im = cap.read()
        if not ok:
            break
        g = cv2.resize(im.max(2), None, fx=S, fy=S, interpolation=cv2.INTER_AREA).astype(np.float32)
        G.append(cv2.GaussianBlur(g, (0, 0), 1.0))
    res = {}
    for n, L in enumerate(lines_of(W)):
        ref = L['ref']; ws = L['words']
        first = min(int(min(W[k]['track'], key=int)) for k in ws); last = max(int(max(W[k]['track'], key=int)) for k in ws)
        pad = int(0.5 * (L['y1'] - L['y0']))
        x0, y0, x1, y1 = L['x0'] - pad, L['y0'] - pad, L['x1'] + pad, L['y1'] + pad
        # template = reference frame; mask = the line's region (ECC compares only there)
        mask = np.zeros(G[ref].shape, np.uint8)
        mask[max(0, int(y0 * S)):int(y1 * S), max(0, int(x0 * S)):int(x1 * S)] = 255
        Hs, ccs = {ref: np.eye(3)}, {ref: 1.0}
        crit = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 60, 1e-5)
        for d in (1, -1):
            Hp = np.eye(3, dtype=np.float32); f = ref + d
            while first - 3 <= f <= last + 3 and 0 <= f < len(G):
                try:
                    cc, Hn = cv2.findTransformECC(G[ref], G[f], Hp.copy(), cv2.MOTION_HOMOGRAPHY, crit, mask, 5)
                except cv2.error:
                    break
                if cc < min_cc:
                    break
                Hs[f], ccs[f] = Hn, cc; Hp = Hn; f += d
        # back to full resolution: H_full = D H_small D^-1 with D = diag(1/S, 1/S, 1)
        D = np.diag([1 / S, 1 / S, 1.0]); Di = np.linalg.inv(D)
        lid = f'line{n:02d}_' + ws[0]
        res[lid] = {'words': ws, 'ref': ref, 'roi': [int(x0), int(y0), int(x1 - x0), int(y1 - y0)],
                    'H': {str(f): [round(float(v), 7) for v in (D @ H @ Di / (D @ H @ Di)[2, 2]).ravel()] for f, H in sorted(Hs.items())},
                    'cc': {str(f): round(float(c), 4) for f, c in sorted(ccs.items())}}
        ks = sorted(Hs)
        print(f'{lid:28s} {len(ws)} mots  ref {ref}  suivi {ks[0]}-{ks[-1]} ({len(ks)} img)')
    json.dump(res, open(out, 'w'))


if __name__ == '__main__':
    main()
