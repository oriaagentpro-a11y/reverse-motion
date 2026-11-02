"""Measurements of the demo video used to write the scenes (step 3 of the method)."""
import sys, json, math
import numpy as np, cv2
sys.path.insert(0, '../../scripts')
from fit_easing import fit
cap = cv2.VideoCapture('src/source.mp4'); FPS = cap.get(cv2.CAP_PROP_FPS); FR = []
while True:
    ok, im = cap.read()
    if not ok: break
    FR.append(im)
def mask(f, rgb, tol=60, roi=None):
    im = FR[f].astype(int); d = np.abs(im - np.array(rgb[::-1])).sum(2) < tol
    if roi: x, y, w, h = roi; m = np.zeros_like(d); m[y:y+h, x:x+w] = d[y:y+h, x:x+w]; d = m
    return d
def box(m):
    ys, xs = np.where(m); return None if not len(xs) else [int(xs.min()), int(ys.min()), int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)]
TEAL, WARM, INK, CREAM = (15, 118, 110), (245, 158, 11), (31, 41, 55), (255, 247, 237)
M = {}
M['title'] = box(mask(75, TEAL, roi=(0, 0, 640, 130)))
op = [(f / FPS, 1 - np.abs(FR[f][40:120, 240:400].astype(int) - FR[75][40:120, 240:400]).mean() / max(1, np.abs(FR[0][40:120, 240:400].astype(int) - FR[75][40:120, 240:400]).mean())) for f in range(20, 40)]
M['title_fade'] = fit([a for a, _ in op], [b for _, b in op])
M['ball_y'] = box(mask(5, TEAL, roi=(0, 130, 640, 230)))
# S2: word pop (height of the ink over the first frames of each word)
pop = [(f / FPS - 16, box(mask(f, WARM))[3]) for f in range(400, 412)]
M['word_full'] = {w: box(mask(f, WARM)) for w, f in zip(['Créer', 'Mesurer', 'Copier', 'Livrer'], [410, 422, 435, 447])}
M['word_pop'] = fit([a for a, _ in pop], [b for _, b in pop])
# S3: square angle and bar
ang = []
for f in range(800, 850):
    c, _ = cv2.findContours(mask(f, TEAL).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    (cx, cy), (w, h), a = cv2.minAreaRect(max(c, key=cv2.contourArea)); ang.append((f / FPS, a, cx, cy, w))
M['square'] = {'cx': round(np.mean([a[2] for a in ang]), 2), 'cy': round(np.mean([a[3] for a in ang]), 2), 'side': round(np.median([a[4] for a in ang]), 2),
               'angle_samples': [(round(t, 2), round(a, 2)) for t, a, *_ in ang[:6]]}
M['bar_track'] = box(mask(1000, (237, 226, 210), tol=20))
bar = [(f / FPS, box(mask(f, WARM, roi=(0, 280, 640, 40)))) for f in range(820, 1200, 40)]
M['bar_fill'] = [(round(t, 2), b[2] if b else 0) for t, b in bar]
# S4: wipe radius (warm pixels along the horizontal axis), counter, label, end card
rad = []
for f in range(1205, 1226):
    row = mask(f, WARM)[180]; xs = np.where(row)[0]
    if len(xs): rad.append((f / FPS, (xs.max() - xs.min() + 1) / 2))
M['wipe'] = fit([a for a, _ in rad if a > 48.25 and _ < 315], [b for a, b in rad if a > 48.25 and b < 315])
M['num_100'] = box(mask(1350, INK, roi=(0, 100, 640, 120))); M['label'] = box(mask(1350, INK, roi=(0, 222, 640, 60)))
M['end_text'] = box(mask(1590, CREAM, roi=(0, 0, 640, 360)))
json.dump(M, open('analysis/measures.json', 'w'), indent=1, default=float); print(json.dumps(M, default=float, indent=0)[:3000])
