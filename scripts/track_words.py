"""Track words (or any small graphic) frame by frame from one clean reference frame, with scale.

Usage: python3 track_words.py <video> <words.json> <out.json> [--min-score 0.6] [--search 70] [--dark]
words.json = [{"id": "s1_what", "text": "What", "ref": 96, "box": [x, y, w, h], "first": 6, "last": 104,
               "weight": 400 (optional)}, ...]
  box = a loose box around the word on frame `ref` (an OCR box is fine): the tight INK box is found inside.
For each word, starting at `ref` and going forward then backward, the ink template (brightest channel,
or darkest with --dark) is searched around the previous position at scales 0.9..1.1 of the previous scale
(normalised cross-correlation). The search stops when the score falls under --min-score (the word is
moving too fast, blurred, rotated in 3D, or gone): those frames get no box, the plate shows the original.
Output: {id: {"text", "ref", "ink_ref": [x, y, w, h], "color": "#RRGGBB", "track": {frame: [x, y, w, h, score]}}}
"""
import sys, os, json
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rmcommon  # noqa: E402
from text_inventory import ink_box  # noqa: E402


def chan(im, dark):
    return (255 - im.min(2)) if dark else im.max(2)


def main():
    a = sys.argv
    video, spec, out = a[1], a[2], a[3]
    min_score = rmcommon.arg(a, 'min-score', 0.6, float); search = rmcommon.arg(a, 'search', 70, int)
    dark = '--dark' in a
    W_ = json.load(open(spec))
    cap = cv2.VideoCapture(video); FR = []
    while True:
        ok, im = cap.read()
        if not ok:
            break
        FR.append(im)
    G = [chan(im, dark).astype(np.float32) for im in FR]
    H, Wd = G[0].shape
    res = {}
    for w in W_:
        ref = w['ref']; bx, by, bw0, bh0 = w['box']; p = int(0.4 * bh0)
        ib = ink_box(FR[ref], [bx - p, by - p, bw0 + 2 * p, bh0 + 2 * p], dark, core=w['box'])
        if not ib:
            print('pas d\'encre :', w['id']); continue
        x, y, bw, bh, _ = ib; pad = max(3, int(0.15 * bh))
        tx0, ty0 = max(0, x - pad), max(0, y - pad)
        tpl = G[ref][ty0:y + bh + pad, tx0:x + bw + pad]
        off = (x - tx0, y - ty0)                     # ink box offset inside the template
        track = {ref: [x, y, bw, bh, 1.0]}
        for direction in (1, -1):
            px, py, ps = x, y, 1.0
            f = ref + direction
            lo, hi = w.get('first', 0), w.get('last', len(FR) - 1)
            while lo <= f <= hi:
                best = None
                for s in np.linspace(ps * 0.9, ps * 1.1, 9):
                    th, tw = int(round(tpl.shape[0] * s)), int(round(tpl.shape[1] * s))
                    if th < 6 or tw < 6:
                        continue
                    t = cv2.resize(tpl, (tw, th), interpolation=cv2.INTER_AREA)
                    sx0, sy0 = max(0, int(px - off[0] * s) - search), max(0, int(py - off[1] * s) - search)
                    sx1, sy1 = min(Wd, int(px - off[0] * s) + tw + search), min(H, int(py - off[1] * s) + th + search)
                    reg = G[f][sy0:sy1, sx0:sx1]
                    if reg.shape[0] < th or reg.shape[1] < tw:
                        continue
                    r = cv2.matchTemplate(reg, t, cv2.TM_CCOEFF_NORMED)
                    _, mv, _, ml = cv2.minMaxLoc(r)
                    if best is None or mv > best[0]:
                        best = (mv, sx0 + ml[0] + off[0] * s, sy0 + ml[1] + off[1] * s, s)
                if not best or best[0] < min_score:
                    break
                mv, nx, ny, s = best
                track[f] = [round(nx, 2), round(ny, 2), round(bw * s, 2), round(bh * s, 2), round(float(mv), 3)]
                px, py, ps = nx, ny, s
                f += direction
        c = FR[ref][y:y + bh, x:x + bw].reshape(-1, 3).astype(np.float32); g = c.max(1)
        bgr = np.median(c[g >= np.percentile(g, 80)], 0)
        res[w['id']] = {'text': w['text'], 'ref': ref, 'ink_ref': [x, y, bw, bh], 'weight': w.get('weight'),
                        'color': '#%02X%02X%02X' % (int(bgr[2]), int(bgr[1]), int(bgr[0])),
                        'track': {str(k): v for k, v in sorted(track.items())}}
        ks = sorted(track)
        print(f"{w['id']:22s} ref {ref}  ink {ib[:4]}  suivi {ks[0]}-{ks[-1]} ({len(ks)} img)  {res[w['id']]['color']}")
    json.dump(res, open(out, 'w'))


if __name__ == '__main__':
    main()
