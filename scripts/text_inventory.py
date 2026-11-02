"""Text inventory: every word of a video, when it is on screen, where, and its ink box on every frame.

Usage: python3 text_inventory.py <video> <out.json> [--step 2] [--jobs 4] [--min-conf 55] [--light | --dark]
1. OCR (tesseract, --psm 11) on every `step`-th frame. Light text on a dark background by default
   (the brightest channel is read, inverted); --dark for dark text on a light background.
2. Words are grouped into instances: same text, boxes overlapping from one OCR frame to the next
   (a word that moves fast keeps its identity as long as its successive boxes touch).
3. For every frame of an instance (including the frames between OCR samples and a few frames before /
   after, where the word fades in or out), the INK box is measured inside the instance's region:
   pixels brighter than the local background -> tight box (x, y, w, h) + mean ink level (opacity cue).
Output: {"fps": .., "w": .., "h": .., "words": [{"id": "w012_trade", "text": "trade", "first": f, "last": f,
         "conf": .., "ocr": {frame: [x, y, w, h]}, "ink": {frame: [x, y, w, h, level]}, "color": "#RRGGBB"}]}
The ink tracks are what a scene replays with RM.fitInk (décalque of every word, frame by frame).
"""
import sys, os, json, re
import numpy as np
import cv2
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rmcommon  # noqa: E402


def ocr_frame(args):
    import pytesseract
    path, f, dark, min_conf = args
    im = cv2.imread(path)
    g = im.min(2) if dark else im.max(2)
    g = cv2.resize(g, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    if not dark:
        g = 255 - g
    d = pytesseract.image_to_data(g, config='--psm 11', output_type=pytesseract.Output.DICT)
    out = []
    for i, t in enumerate(d['text']):
        t = t.strip()
        if not t or float(d['conf'][i]) < min_conf or not re.search(r'[A-Za-z0-9$%]', t):
            continue
        out.append({'text': t, 'box': [d['left'][i] // 2, d['top'][i] // 2, d['width'][i] // 2, d['height'][i] // 2],
                    'conf': float(d['conf'][i])})
    return f, out


def iou(a, b):
    ax1, ay1, bx1, by1 = a[0] + a[2], a[1] + a[3], b[0] + b[2], b[1] + b[3]
    iw, ih = max(0, min(ax1, bx1) - max(a[0], b[0])), max(0, min(ay1, by1) - max(a[1], b[1]))
    inter = iw * ih
    return inter / max(1, a[2] * a[3] + b[2] * b[3] - inter)


def ink_box(img, roi, dark, core=None):
    """Tight ink box of the text inside `roi`. With `core` (the word's own box, e.g. from OCR), only the
    connected ink components whose centre lies inside `core` are kept: a neighbouring word or a glow that
    enters the ROI does not inflate the box."""
    x, y, w, h = [int(v) for v in roi]
    H, W = img.shape[:2]
    x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + w), min(H, y + h)
    if x1 - x0 < 3 or y1 - y0 < 3:
        return None
    c = img[y0:y1, x0:x1]
    g = (c.min(2) if dark else c.mean(2)).astype(np.float32)   # light text: mean of channels (white on blue AND blue on black)
    bg = np.median(np.concatenate([g[0], g[-1], g[:, 0], g[:, -1]]))   # background level on the ROI border
    diff = (bg - g) if dark else (g - bg)
    m = diff > max(40.0, 0.45 * float(diff.max()) if diff.size else 40.0)
    m = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    if core is not None:
        cx0, cy0, cw, ch = core
        n, lab, st, cen = cv2.connectedComponentsWithStats(m)
        keep = np.zeros(n, bool)
        for i in range(1, n):
            px, py = cen[i][0] + x0, cen[i][1] + y0
            if cx0 <= px <= cx0 + cw and cy0 <= py <= cy0 + ch and st[i, 4] >= 4:
                keep[i] = True
        m = keep[lab]
    m = m > 0
    if m.sum() < 12:
        return None
    ys, xs = np.where(m)
    level = float(np.percentile(diff[m], 90))
    return [int(x0 + xs.min()), int(y0 + ys.min()), int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1), round(level, 1)]


def main():
    a = sys.argv
    video, out = a[1], a[2]
    step = rmcommon.arg(a, 'step', 2, int); jobs = rmcommon.arg(a, 'jobs', 4, int)
    min_conf = rmcommon.arg(a, 'min-conf', 55, float); dark = '--dark' in a
    V = rmcommon.probe(video)
    tmp = out + '_frames'; os.makedirs(tmp, exist_ok=True)
    cap = cv2.VideoCapture(video); FR = []
    while True:
        ok, im = cap.read()
        if not ok:
            break
        FR.append(im)
    todo = []
    for f in range(0, len(FR), step):
        p = os.path.join(tmp, f'{f:05d}.png'); cv2.imwrite(p, FR[f]); todo.append((p, f, dark, min_conf))
    with ProcessPoolExecutor(jobs) as ex:
        res = dict(ex.map(ocr_frame, todo))
    # group into instances
    inst = []
    for f in sorted(res):
        for wd in res[f]:
            best = None
            for it in inst:
                if it['text'].lower() == wd['text'].lower() and f - it['last'] <= 3 * step and iou(it['ocr'][it['last']], wd['box']) > 0.15:
                    best = it if best is None or it['last'] > best['last'] else best
            if best:
                best['ocr'][f] = wd['box']; best['last'] = f; best['conf'] = max(best['conf'], wd['conf'])
            else:
                inst.append({'text': wd['text'], 'first': f, 'last': f, 'conf': wd['conf'], 'ocr': {f: wd['box']}})
    inst = [it for it in inst if len(it['ocr']) >= 2 or it['conf'] >= 85]
    inst.sort(key=lambda it: (it['first'], it['ocr'][it['first']][1], it['ocr'][it['first']][0]))
    # ink tracks (with a margin of frames on both sides: fades in and out)
    for n, it in enumerate(inst):
        it['id'] = f"w{n:03d}_" + re.sub(r'[^A-Za-z0-9]', '', it['text'])[:12]
        ks = sorted(it['ocr']); ink = {}
        for f in range(max(0, it['first'] - 2 * step), min(len(FR), it['last'] + 2 * step + 1)):
            k0 = max([k for k in ks if k <= f], default=ks[0]); k1 = min([k for k in ks if k >= f], default=ks[-1])
            b0, b1 = it['ocr'][k0], it['ocr'][k1]
            p = 0 if k1 == k0 else (f - k0) / (k1 - k0)
            b = [b0[i] + (b1[i] - b0[i]) * p for i in range(4)]
            pad = int(0.35 * b[3]) + 4
            r = ink_box(FR[f], [int(b[0] - pad), int(b[1] - pad), int(b[2] + 2 * pad), int(b[3] + 2 * pad)], dark)
            if r:
                ink[f] = r
        it['ink'] = {str(k): v for k, v in ink.items()}
        it['ocr'] = {str(k): v for k, v in it['ocr'].items()}
        # colour: median of the ink pixels on the frame where the word is the most visible
        if ink:
            fb = max(ink, key=lambda k: ink[k][4]); x, y, w, h, _ = ink[fb]
            c = FR[fb][y:y + h, x:x + w].reshape(-1, 3).astype(np.float32)
            g = c.min(1) if dark else c.max(1)
            sel = c[g <= np.percentile(g, 25)] if dark else c[g >= np.percentile(g, 75)]
            bgr = np.median(sel, 0)
            it['color'] = '#%02X%02X%02X' % (int(bgr[2]), int(bgr[1]), int(bgr[0]))
            it['peak_frame'] = int(fb)
    json.dump({'fps': V['fps'], 'w': V['w'], 'h': V['h'], 'words': inst}, open(out, 'w'), indent=0)
    for it in inst:
        print(f"{it['id']:22s} {it['first']:4d}-{it['last']:4d}  conf {it['conf']:.0f}  {it.get('color', '')}  ink {len(it['ink'])} img")
    print(f'{len(inst)} mots -> {out}')


if __name__ == '__main__':
    main()
