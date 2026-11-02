"""Ghost guard: find the frames where a rebuilt element does NOT match the original, and hide it there.

In décalque mode the plate (measured on the original) lies under the rebuilt elements. When a rebuilt text,
icon or button is off (wrong frame, wrong position, different glyphs, motion-blurred in the original...), the
viewer sees it ON TOP of the plate: doubled letters, a word that arrives early, an icon that should not be
there. A global SSIM hides these (they cover a few % of the frame). This tool checks every element, every frame.

Usage: python3 ghost_guard.py <scene.html> <original.mp4> <copy.mp4> <copy_first_frame> <f0> <f1> <out_hide.js>
                              [--ssim 0.75] [--extra 0.12] [--pad 6] [--ids a,b,c] [--report out.json]
copy.mp4: the scene rendered from global frame <copy_first_frame> (render.mjs), or the full reproduction (0).
For each frame and each element of window.__rmFg (the fgIds given to RMGL.decalque) that is visible:
  crop = element box + pad, in the original and in the copy;
  ssim  = SSIM of the two crops (grey);
  extra = share of the copy's edges that have no edge within 2 px in the original (a ghost = edges that
          should not be there).
  ghost if ssim < --ssim  or  (extra > --extra and the copy has edges there).
Writes window.HIDE = {frame: [ids]}. RMGL.decalque hides those elements in those frames (plate active), also in
hole renders, so the next plate extraction keeps the ORIGINAL pixels there. Then: holes -> plate -> render ->
run the guard again (it must report 0).
"""
import sys, os, json
import numpy as np
import cv2
from skimage.metrics import structural_similarity
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rmcommon  # noqa: E402

JS_BOXES = """ids => ids.map(id => { const e = document.getElementById(id); if (!e) return null;
  if (e.classList.contains('rm-ghost')) return 'guarded';  // already hidden by a previous run: keep it hidden
  let o = 1, n = e; while (n && n.nodeType === 1) { const cs = getComputedStyle(n);
    if (cs.display === 'none' || cs.visibility === 'hidden') return null; o *= +cs.opacity; n = n.parentElement || n.parentNode; }
  if (o < 0.08) return null; const r = e.getBoundingClientRect(); if (r.width < 2 || r.height < 2) return null;
  return [r.x, r.y, r.width, r.height, o]; })"""


def read_range(path, start, f0, f1):
    cap = cv2.VideoCapture(path); cap.set(cv2.CAP_PROP_POS_FRAMES, f0 - start); out = {}
    for f in range(f0, f1 + 1):
        ok, im = cap.read()
        if not ok:
            break
        out[f] = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    return out


def main():
    a = sys.argv
    scene, orig, copy, cstart, f0, f1, out = a[1], a[2], a[3], int(a[4]), int(a[5]), int(a[6]), a[7]
    thr_s = rmcommon.arg(a, 'ssim', 0.75, float); thr_e = rmcommon.arg(a, 'extra', 0.12, float)
    pad = rmcommon.arg(a, 'pad', 6, int); only = rmcommon.arg(a, 'ids'); only = only.split(',') if only else None
    V = rmcommon.probe(orig)
    O = read_range(orig, 0, f0, f1); C = read_range(copy, cstart, f0, f1)
    k = np.ones((5, 5), np.uint8)
    hide, rows = {}, []
    with sync_playwright() as pw:
        br = rmcommon.launch(pw); page = br.new_page(viewport={'width': V['w'], 'height': V['h']}, device_scale_factor=1)
        page.goto(rmcommon.scene_url(scene, V['fps'])); page.wait_for_function('window.__rm && window.__rm.ready === true')
        ids = only or page.evaluate('window.__rmFg || []')
        if not ids:
            sys.exit('la scène n\'expose aucun élément (window.__rmFg vide : RMGL.decalque({fgIds}) requis)')
        for f in range(f0, f1 + 1):
            if f not in O or f not in C:
                continue
            page.evaluate(f'void window.__rm.seek({f / V["fps"]})')
            boxes = page.evaluate(JS_BOXES, ids)
            for el, b in zip(ids, boxes):
                if b == 'guarded':
                    hide.setdefault(f, []).append(el); continue
                if not b:
                    continue
                x0, y0 = max(0, int(b[0] - pad)), max(0, int(b[1] - pad))
                x1, y1 = min(V['w'], int(b[0] + b[2] + pad)), min(V['h'], int(b[1] + b[3] + pad))
                if x1 - x0 < 8 or y1 - y0 < 8:
                    continue
                o, c = O[f][y0:y1, x0:x1], C[f][y0:y1, x0:x1]
                win = min(7, (min(o.shape) // 2) * 2 + 1)
                s = structural_similarity(o, c, data_range=255, win_size=win) if win >= 3 else 1.0
                eo, ec = cv2.Canny(o, 60, 160), cv2.Canny(c, 60, 160)
                n_c = int((ec > 0).sum()); eol = cv2.Canny(o, 20, 60)  # low threshold on the reference side
                extra = float(((ec > 0) & (cv2.dilate(eol, k) == 0)).sum()) / max(1, n_c)
                ghost = s < thr_s or (extra > thr_e and n_c > 40)
                rows.append({'frame': f, 'id': el, 'ssim': round(float(s), 3), 'extra': round(extra, 3), 'ghost': bool(ghost)})
                if ghost:
                    hide.setdefault(f, []).append(el)
        br.close()
    # close short gaps (<= 3 frames) between hidden frames of the same element: no flicker code <-> plate
    for el in ids:
        fs = sorted(f for f, v in hide.items() if el in v)
        for p, q in zip(fs, fs[1:]):
            if 1 < q - p <= 4:
                for f in range(p + 1, q):
                    if el not in hide.setdefault(f, []):
                        hide[f].append(el)
    with open(out, 'w') as fh:
        fh.write('// ghost_guard.py ' + ' '.join(a[1:]) + '\n')
        fh.write('window.HIDE = ' + json.dumps({str(f): v for f, v in sorted(hide.items())}) + ';\n')
    if rmcommon.arg(a, 'report'):
        json.dump(rows, open(rmcommon.arg(a, 'report'), 'w'))
    by_id = {}
    for f, v in hide.items():
        for el in v:
            by_id.setdefault(el, []).append(f)
    print(f'{sum(len(v) for v in hide.values())} fantômes sur {len(hide)} images -> {out}')
    for el, fs in sorted(by_id.items()):
        fs.sort(); runs, s0 = [], fs[0]
        for p, q in zip(fs, fs[1:] + [None]):
            if q != p + 1:
                runs.append(f'{s0}-{p}' if p > s0 else f'{p}'); s0 = q
        print(f'  {el}: {", ".join(runs)}')


if __name__ == '__main__':
    main()
