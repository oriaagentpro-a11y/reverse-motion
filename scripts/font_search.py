"""Search a whole font catalogue for the closest match to words seen in a video.

Usage: python3 font_search.py <targets.json> <fonts_dir> <out.json> [--top 15]
targets.json = [{"frame": "f.png", "box": [x, y, w, h], "word": "blank", "weight": 700, "dark_bg": false}, ...]
For every .ttf under fonts_dir (variable fonts are set to the asked weight, plus/minus 100),
each word is rendered, cropped to its ink and resized to the target's ink box. Score per word:
shape overlap (IoU) minus a penalty for a different width/height ratio. A font's score is its
mean over all words; the best weight per word is kept.
"""
import sys, os, json, glob, math
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont


def ink(mask):
    ys, xs = np.where(mask)
    return mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def target_mask(t):
    img = cv2.imread(t['frame'])
    x, y, w, h = t['box']
    g = cv2.cvtColor(img[y:y + h, x:x + w], cv2.COLOR_BGR2GRAY)
    if t.get('dark_bg'):
        g = 255 - g
    _, m = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    m = ink(m > 0)
    return cv2.resize(m.astype(np.uint8) * 255, (m.shape[1] * 4, m.shape[0] * 4), interpolation=cv2.INTER_CUBIC) > 127


def render(font, word):
    im = Image.new('L', (220 * len(word) + 200, 500), 0)
    ImageDraw.Draw(im).text((40, 60), word, font=font, fill=255)
    a = np.array(im) > 127
    return ink(a) if a.any() else None


def compare(tm, rm):
    th, tw = tm.shape
    ratio_t, ratio_r = tw / th, rm.shape[1] / rm.shape[0]
    r = cv2.resize(rm.astype(np.uint8) * 255, (tw, th), interpolation=cv2.INTER_AREA) > 127
    iou = (tm & r).sum() / max(1, (tm | r).sum())
    return iou - 0.6 * abs(math.log(ratio_r / ratio_t))


def load(path, weight):
    f = ImageFont.truetype(path, 200)
    try:
        axes = f.get_variation_axes()
    except Exception:
        axes = None
    if axes:
        vals = []
        for a in axes:
            name = a.get('name', b'')
            name = name.decode() if isinstance(name, bytes) else str(name)
            if name.lower().startswith('weight') or a.get('tag') == 'wght':
                vals.append(min(a['maximum'], max(a['minimum'], weight)))
            else:
                vals.append(a.get('default', a['minimum']))
        f.set_variation_by_axes(vals)
        return f
    base = os.path.basename(path)
    if weight >= 600 and 'Bold' not in base:
        return None
    if weight < 600 and 'Bold' in base:
        return None
    return f


def main():
    targets = json.load(open(sys.argv[1])); fonts_dir = sys.argv[2]; out = sys.argv[3]
    top = int(sys.argv[sys.argv.index('--top') + 1]) if '--top' in sys.argv else 15
    tms = [target_mask(t) for t in targets]
    files = sorted(glob.glob(os.path.join(fonts_dir, '**', '*.ttf'), recursive=True))
    fam = {}
    for path in files:
        family = os.path.basename(os.path.dirname(path))
        for i, t in enumerate(targets):
            for dw in (-100, 0, 100):
                try:
                    f = load(path, t['weight'] + dw)
                except Exception:
                    f = None
                if f is None:
                    continue
                rm = render(f, t['word'])
                if rm is None:
                    continue
                s = compare(tms[i], rm)
                key = (family, i)
                if s > fam.get(key, (-9, None))[0]:
                    fam[key] = (s, t['weight'] + dw, os.path.relpath(path, fonts_dir))
    agg = {}
    for (family, i), (s, w, p) in fam.items():
        agg.setdefault(family, {'family': family, 'scores': {}, 'weights': {}, 'file': p})
        agg[family]['scores'][targets[i]['word']] = round(float(s), 4)
        agg[family]['weights'][targets[i]['word']] = w
    rows = [r for r in agg.values() if len(r['scores']) == len(targets)]
    for r in rows:
        r['mean'] = round(float(np.mean(list(r['scores'].values()))), 4)
    rows.sort(key=lambda r: -r['mean'])
    json.dump(rows[:top], open(out, 'w'), indent=1)
    for r in rows[:top]:
        print(f"{r['family']:28s} {r['mean']:.4f} {r['scores']} {r['weights']}")


if __name__ == '__main__':
    main()
