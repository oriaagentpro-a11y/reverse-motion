"""Find the closest font to a word crop taken from a video frame.

Usage: python3 match_font.py <frame.png> <x> <y> <w> <h> <word> <weight> <fonts_dir> [--dark-bg]
Crops the word, binarises it, renders the same word in every candidate font
at the same ink height and scores the overlap (IoU). Prints a ranking as JSON.
"""
import sys, json, glob, os
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont


def ink_mask(img, dark_bg):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if dark_bg:
        g = 255 - g
    _, m = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    return m > 0


def tight(m):
    ys, xs = np.where(m)
    return m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def render(word, font_path, height):
    big = 400
    font = ImageFont.truetype(font_path, big)
    im = Image.new('L', (big * len(word), big * 2), 0)
    ImageDraw.Draw(im).text((20, 20), word, font=font, fill=255)
    m = tight(np.array(im) > 127)
    scale = height / m.shape[0]
    w = max(1, round(m.shape[1] * scale))
    return cv2.resize(m.astype(np.uint8) * 255, (w, height), interpolation=cv2.INTER_AREA) > 127


def score(target, cand):
    h = target.shape[0]
    w = max(target.shape[1], cand.shape[1])
    a = np.zeros((h, w), bool); a[:, :target.shape[1]] = target
    b = np.zeros((h, w), bool); b[:, :cand.shape[1]] = cand
    iou = (a & b).sum() / max(1, (a | b).sum())
    width_ratio = cand.shape[1] / target.shape[1]
    return iou, width_ratio


def main():
    frame, x, y, w, h, word, weight, fonts_dir = sys.argv[1:9]
    dark = '--dark-bg' in sys.argv
    img = cv2.imread(frame)
    x, y, w, h = map(int, (x, y, w, h))
    target = tight(ink_mask(img[y:y + h, x:x + w], dark))
    up = 4
    target = cv2.resize(target.astype(np.uint8) * 255, (target.shape[1] * up, target.shape[0] * up),
                        interpolation=cv2.INTER_CUBIC) > 127
    rows = []
    for p in sorted(glob.glob(os.path.join(fonts_dir, f'*-{weight}.ttf'))):
        iou, wr = score(target, render(word, p, target.shape[0]))
        rows.append({'font': os.path.basename(p).rsplit('-', 1)[0], 'iou': round(float(iou), 4),
                     'width_ratio': round(float(wr), 3)})
    rows.sort(key=lambda r: -r['iou'])
    print(json.dumps(rows, indent=1))


if __name__ == '__main__':
    main()
