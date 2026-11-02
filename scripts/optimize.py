"""Automatic correction loop: tune scene parameters to maximise a fidelity score on a frame range.

Score = 0.6 x SSIM + 0.4 x (1 - mean absolute pixel error / 40), so hiding an element never pays.

Usage: python3 optimize.py <scene.html> <original.mp4> <spec.json> <out_params.json> [--rounds 3]
spec.json = {"frames": [start, end, step], "base": {...current overrides...},
             "params": {"ripple.w": [min, max], "blobRScale": [min, max], ...}}
The scene reads overrides from its URL hash (JSON). Coordinate descent: each parameter is
tried at several values, the best is kept, the step shrinks every round. Prints the score
before and after; writes the best overrides (merged with base) to out_params.json.
"""
import sys, json, copy, os, urllib.parse
import numpy as np
import cv2
from skimage.metrics import structural_similarity
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rmcommon  # noqa: E402


def _key(k):
    return int(k) if k.isdigit() else k


def set_path(d, path, v, defaults=None):
    keys = [_key(k) for k in path.split('.')]
    for i, k in enumerate(keys[:-1]):
        if isinstance(d, list):
            d = d[k]
            continue
        if k not in d:
            base = get_path(defaults or {}, '.'.join(map(str, keys[:i + 1])), None)
            d[k] = copy.deepcopy(base) if base is not None else ([] if isinstance(keys[i + 1], int) else {})
        d = d[k]
    d[keys[-1]] = v


def get_path(d, path, default):
    for k in path.split('.'):
        k = _key(k)
        if isinstance(d, list) and isinstance(k, int) and k < len(d):
            d = d[k]
        elif isinstance(d, dict) and k in d:
            d = d[k]
        else:
            return default
    return d


def main():
    scene, orig, spec_path, out = sys.argv[1:5]
    V = rmcommon.probe(orig)  # frame rate and size come from the source, never from constants
    rounds = int(sys.argv[sys.argv.index('--rounds') + 1]) if '--rounds' in sys.argv else 3
    spec = json.load(open(spec_path))
    fr = spec['frames']
    frames = list(range(*fr)) if len(fr) == 3 and fr[1] > fr[0] and not spec.get('explicit') else fr
    cap = cv2.VideoCapture(orig)
    ref = {}
    for f in frames:
        cap.set(cv2.CAP_PROP_POS_FRAMES, f); ok, img = cap.read()
        ref[f] = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    defaults = spec.get('defaults', {})
    with sync_playwright() as pw:
        br = rmcommon.launch(pw)
        page = br.new_page(viewport={'width': V['w'], 'height': V['h']}, device_scale_factor=1)
        url = rmcommon.scene_url(scene, V['fps'])

        def score(params):
            page.goto(url + '#' + urllib.parse.quote(json.dumps(params)))
            page.reload()
            page.wait_for_function('window.__rm && window.__rm.ready === true')
            vals = []
            for f in frames:
                page.evaluate(f'(async () => {{ window.__rm.seek({f / V["fps"]}); if (window.__rmWait && await window.__rmWait()) window.__rm.seek({f / V["fps"]}); }})()')
                buf = page.screenshot()
                img = cv2.imdecode(np.frombuffer(buf, np.uint8), cv2.IMREAD_GRAYSCALE)
                ssim = structural_similarity(ref[f], img, data_range=255)
                mae = float(np.abs(ref[f].astype(float) - img).mean())
                # SSIM alone rewards hiding what does not match; the pixel error term keeps content honest
                vals.append(0.6 * ssim + 0.4 * max(0.0, 1 - mae / 40))
            return float(np.mean(vals))

        best = copy.deepcopy(spec.get('base', {}))
        best_s = score(best)
        print(f'start score {best_s:.4f}', flush=True)
        for r in range(rounds):
            for name, (lo, hi) in spec['params'].items():
                cur = get_path(best, name, get_path(defaults, name, (lo + hi) / 2))
                span = (hi - lo) / (2 ** (r + 1))
                for cand in [cur - span, cur - span / 2, cur + span / 2, cur + span]:
                    cand = float(min(hi, max(lo, cand)))
                    trial = copy.deepcopy(best); set_path(trial, name, round(cand, 4), defaults)
                    s = score(trial)
                    if s > best_s + 1e-5:
                        best, best_s, cur = trial, s, cand
                print(f'round {r + 1} {name} = {get_path(best, name, cur)}  score {best_s:.4f}', flush=True)
        br.close()
    json.dump(best, open(out, 'w'), indent=1)
    print(f'best score {best_s:.4f} -> {out}')


if __name__ == '__main__':
    main()
