"""Per-frame registration ("recalage image par image") of rebuilt elements onto the original.

For every frame of a range, a small correction transform (dx, dy, scale, rotation) is searched for
one element so that the rendered region matches the original as closely as possible. The search
starts from the previous frame's answer (motion is continuous), uses shrinking steps, and scores
SSIM + pixel error inside a region of interest. The answers are written as a track that the scene
replays (RM.applyReg) on top of its animation: the trajectory then follows the original trait for trait.

Usage: python3 register.py <scene.html> <original.mp4> <spec.json> <out_tracks.js>
spec = {"frames": [f0, f1],                       # inclusive range, global frame indices
        "elements": [{"id": "starts", "roi": [x, y, w, h] | "auto", "params": ["dx", "dy", "s", "r"],
                      "frames": [f0, f1] (optional), "pad": 24}],
        "hash": {...}}                            # optional scene overrides
Element option "ink": {"color": "5000B0", "tol": 110}: compare only the pixels of the element's own colour
(soft mask of the distance to that colour) instead of grey levels. The match then ignores whatever lies
behind the element (code shapes, plate, holes): register in ink mode BEFORE punching plate holes.
The output file sets window.REG = {frame: {elementId: {dx, dy, s, r}}} (merged with an existing file).
"""
import sys, os, json, re, urllib.parse
import numpy as np
import cv2
from skimage.metrics import structural_similarity
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rmcommon  # noqa: E402
STEPS = {'dx': [4, 2, 1, 0.5, 0.25], 'dy': [4, 2, 1, 0.5, 0.25], 's': [0.04, 0.02, 0.01, 0.005], 'r': [2, 1, 0.5, 0.25], 'o': [0.2, 0.1, 0.05, 0.025]}
NEUTRAL = {'dx': 0.0, 'dy': 0.0, 's': 1.0, 'r': 0.0, 'o': 1.0}
# Guard rails: an element may be moved, never hidden. Scale and offsets stay in a plausible window,
# otherwise the search "wins" by shrinking a misplaced element to nothing.
LIMITS = {'dx': (-40, 40), 'dy': (-40, 40), 's': (0.8, 1.25), 'r': (-15, 15), 'o': (0.0, 1.0)}


def load_existing(path):
    if not os.path.exists(path):
        return {}
    txt = open(path).read()
    m = re.search(r'window\.REG\s*=\s*(\{.*\});', txt, re.S)
    return json.loads(m.group(1)) if m else {}


def main():
    scene, orig, spec_path, out = sys.argv[1:5]
    V = rmcommon.probe(orig)  # frame rate and size come from the source, never from constants
    spec = json.load(open(spec_path))
    reg = load_existing(out)
    # Read every needed frame ONCE, sequentially: OpenCV seeking backwards in H.264 can return wrong frames
    # (it happened when moving from one element to the next), which silently corrupts the comparison.
    lo = min(el.get('frames', spec['frames'])[0] for el in spec['elements'])
    hi = max(el.get('frames', spec['frames'])[1] for el in spec['elements'])
    cap = cv2.VideoCapture(orig); cap.set(cv2.CAP_PROP_POS_FRAMES, lo); FR = {}
    for fi in range(lo, hi + 1):
        ok, im = cap.read()
        if not ok:
            break
        FR[fi] = im
    with sync_playwright() as pw:
        br = rmcommon.launch(pw)
        page = br.new_page(viewport={'width': V['w'], 'height': V['h']}, device_scale_factor=1)
        url = rmcommon.scene_url(scene, V['fps'], hash_obj=spec.get('hash'))
        page.goto(url); page.wait_for_function('window.__rm && window.__rm.ready === true')
        for el in spec['elements']:
            f0, f1 = el.get('frames', spec['frames'])
            prev = dict(NEUTRAL)
            for f in range(f0, f1 + 1):
                if f not in FR:
                    continue
                ref = FR[f]
                refg = cv2.cvtColor(ref, cv2.COLOR_BGR2GRAY)
                page.evaluate('([f, r]) => { window.REG = window.REG || {}; window.REG[f] = r; }', [f, reg.get(str(f), {})])
                if el.get('roi', 'auto') == 'auto':
                    page.evaluate(f'(async () => {{ window.__rm.seek({f / V["fps"]}); if (window.__rmWait && await window.__rmWait()) window.__rm.seek({f / V["fps"]}); }})()')
                    bb = page.evaluate("id => { const e = document.getElementById(id); if (!e) return null; const r = e.getBoundingClientRect(); return [r.x, r.y, r.width, r.height]; }", el['id'])
                    if not bb or bb[2] < 1:
                        continue
                    p = el.get('pad', 24)
                    x0, y0 = max(0, int(bb[0] - p)), max(0, int(bb[1] - p))
                    x1, y1 = min(V['w'], int(bb[0] + bb[2] + p)), min(V['h'], int(bb[1] + bb[3] + p))
                else:
                    x, y, w, h = el['roi']; x0, y0, x1, y1 = x, y, x + w, y + h
                if x1 - x0 < 8 or y1 - y0 < 8:
                    continue
                tgt = refg[y0:y1, x0:x1]
                ink = el.get('ink')
                if ink:
                    IC = np.array([int(ink['color'][i:i + 2], 16) for i in (4, 2, 0)], np.float32); itol = float(ink.get('tol', 110))
                    inkmask = lambda bgr: np.clip(1 - np.linalg.norm(bgr.astype(np.float32) - IC, axis=2) / itol, 0, 1)
                    tgt_ink = cv2.GaussianBlur(inkmask(ref[y0:y1, x0:x1]), (0, 0), 0.8)

                def score(params):
                    r = dict(reg.get(str(f), {})); r[el['id']] = params
                    page.evaluate('([f, r]) => { window.REG[f] = r; }', [f, r])
                    page.evaluate(f'(async () => {{ window.__rm.seek({f / V["fps"]}); if (window.__rmWait && await window.__rmWait()) window.__rm.seek({f / V["fps"]}); }})()')
                    buf = page.screenshot(clip={'x': x0, 'y': y0, 'width': x1 - x0, 'height': y1 - y0})
                    if ink:
                        col = cv2.imdecode(np.frombuffer(buf, np.uint8), cv2.IMREAD_COLOR)
                        mi = cv2.GaussianBlur(inkmask(col), (0, 0), 0.8)
                        if mi.shape != tgt_ink.shape:
                            mi = cv2.resize(mi, (tgt_ink.shape[1], tgt_ink.shape[0]))
                        inter = np.minimum(mi, tgt_ink).sum(); uni = np.maximum(mi, tgt_ink).sum()
                        return float(inter / max(uni, 1e-6))
                    img = cv2.imdecode(np.frombuffer(buf, np.uint8), cv2.IMREAD_GRAYSCALE)
                    if img.shape != tgt.shape:
                        img = cv2.resize(img, (tgt.shape[1], tgt.shape[0]))
                    win = 7 if min(tgt.shape) >= 7 else (min(tgt.shape) // 2) * 2 + 1
                    ss = structural_similarity(tgt, img, data_range=255, win_size=win)
                    mae = float(np.abs(tgt.astype(float) - img).mean())
                    return 0.6 * ss + 0.4 * max(0.0, 1 - mae / 40)

                lim = {k: tuple(el.get('limits', {}).get(k, LIMITS[k])) for k in LIMITS}
                if ink:  # skip frames where the element is not really visible in the original (occluded, fading, not born)
                    page.evaluate('([f, r]) => { window.REG[f] = r; }', [f, reg.get(str(f), {})])
                    page.evaluate(f'(async () => {{ window.__rm.seek({f / V["fps"]}); if (window.__rmWait && await window.__rmWait()) window.__rm.seek({f / V["fps"]}); }})()')
                    col0 = cv2.imdecode(np.frombuffer(page.screenshot(clip={'x': x0, 'y': y0, 'width': x1 - x0, 'height': y1 - y0}), np.uint8), cv2.IMREAD_COLOR)
                    own = float(inkmask(col0).sum()); seen = float(tgt_ink.sum())
                    if seen < max(15.0, el.get('min_visible', 0.35) * own):
                        print(f"frame {f} {el['id']}: skipped (visible ink {seen:.0f} vs {own:.0f}) roi {x0},{y0},{x1},{y1}", flush=True)
                        continue
                cur = dict(prev); best = score(cur); base = score(dict(NEUTRAL)) if cur != NEUTRAL else best
                if base > best:
                    cur, best = dict(NEUTRAL), base
                # coarse grid on the offsets first (escapes local optima), then shrinking coordinate steps
                if 'dx' in el.get('params', ['dx', 'dy']) and (f == f0 or best < el.get('regrid', 0.75)):
                    c0 = dict(cur); g = el.get('grid', 12)
                    for gx in range(-g, g + 1, 4):
                        for gy in range(-g, g + 1, 4):
                            cand = dict(c0); cand['dx'] = c0['dx'] + gx; cand['dy'] = c0['dy'] + gy
                            if not (lim['dx'][0] <= cand['dx'] <= lim['dx'][1] and lim['dy'][0] <= cand['dy'] <= lim['dy'][1]):
                                continue
                            sc = score(cand)
                            if sc > best + 1e-5:
                                cur, best = cand, sc
                for level in range(5):
                    improved = True
                    while improved:
                        improved = False
                        for k in el.get('params', ['dx', 'dy']):
                            st = STEPS[k][min(level, len(STEPS[k]) - 1)]
                            for sgn in (1, -1):
                                cand = dict(cur); cand[k] = round(cur[k] + sgn * st, 4)
                                if not (lim[k][0] <= cand[k] <= lim[k][1]):
                                    continue
                                sc = score(cand)
                                if sc > best + 1e-5:
                                    cur, best, improved = cand, sc, True
                                    break
                at_limit = any(abs(cur[k] - lim[k][0]) < 1e-6 or abs(cur[k] - lim[k][1]) < 1e-6 for k in el.get('params', ['dx', 'dy']) if k != 'o')
                if best < el.get('min_score', 0.45) or at_limit:
                    print(f"frame {f} {el['id']}: rejected {cur} score {best:.4f}{' (at limit)' if at_limit else ''}", flush=True)
                    continue
                reg.setdefault(str(f), {})[el['id']] = {k: v for k, v in cur.items() if v != NEUTRAL[k]}
                prev = cur
                print(f"frame {f} {el['id']}: {cur}  score {best:.4f}", flush=True)
        br.close()
    # outlier filter: a correction far from the median of its neighbours (+-3 frames) is a mis-registration
    for el in spec['elements']:
        fs = sorted(int(f) for f in reg if el['id'] in reg[f])
        drop = []
        for f in fs:
            nb = [reg[str(g)][el['id']] for g in fs if g != f and abs(g - f) <= 3]
            if len(nb) < 2:
                continue
            for k in ('dx', 'dy'):
                med = float(np.median([n.get(k, 0.0) for n in nb]))
                if abs(reg[str(f)][el['id']].get(k, 0.0) - med) > el.get('outlier_px', 4):
                    drop.append(f); break
        for f in drop:
            reg[str(f)].pop(el['id'], None)
        if drop:
            print(f"{el['id']}: {len(drop)} outlier frames removed {drop}", flush=True)
    with open(out, 'w') as fh:
        fh.write('window.REG = ' + json.dumps(reg) + ';\n')
    print(f'registration -> {out}')


if __name__ == '__main__':
    main()
