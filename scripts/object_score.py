"""Local fidelity of a modelled 3D object: its rendered frames (RGBA) laid over the video, compared in its zone.

Usage: python3 object_score.py <video> <frames_dir> <pose.json> [--bg render.mp4] [--sheet out.png] [--every 6]
                               [--json out.json]
For each rendered frame f_XXXXX.png, the RGBA image is laid over the background (the video itself, or the
scene's render with --bg) and compared with the video in the object's zone (its quad + 15 %):
SSIM (grey) and mean Delta E 2000. The source pixels under the object are entirely replaced by the render, so
a high score means the MODEL reproduces the object, not that the plate kept it (P35).
--sheet: contact sheet "video | model | difference x4" every --every frames, to look at before believing a score.
"""
import sys, os, json, glob, re
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rmcommon  # noqa: E402
from skimage.metrics import structural_similarity as ssim  # noqa: E402
from skimage.color import rgb2lab, deltaE_ciede2000  # noqa: E402


def over(bg, rgba):
    a = rgba[..., 3:4].astype(np.float32) / 255
    return (rgba[..., :3].astype(np.float32) * a + bg.astype(np.float32) * (1 - a)).astype(np.uint8)


def main():
    a = sys.argv
    video, fdir, pose = a[1], a[2], json.load(open(a[3]))
    bgv = rmcommon.arg(a, 'bg', None); sheet = rmcommon.arg(a, 'sheet', None); every = rmcommon.arg(a, 'every', 6, int)
    files = sorted(glob.glob(os.path.join(fdir, 'f_*.png')))
    cap = cv2.VideoCapture(video); capb = cv2.VideoCapture(bgv) if bgv else None
    rows, res = [], {}
    for fp in files:
        f = int(re.findall(r'(\d+)', os.path.basename(fp))[0])
        p = pose['frames'].get(str(f))
        if not p:
            continue
        cap.set(cv2.CAP_PROP_POS_FRAMES, f); ok, src = cap.read()
        if capb:
            capb.set(cv2.CAP_PROP_POS_FRAMES, f); ok2, bg = capb.read()
        else:
            bg = src
        rgba = cv2.imread(fp, cv2.IMREAD_UNCHANGED)
        comp = over(bg, rgba)
        q = np.array(p['quad']); mg = 0.15 * (q[:, 0].max() - q[:, 0].min())
        x0, y0 = int(max(0, q[:, 0].min() - mg)), int(max(0, q[:, 1].min() - mg))
        x1, y1 = int(min(src.shape[1], q[:, 0].max() + mg)), int(min(src.shape[0], q[:, 1].max() + mg))
        A, B = src[y0:y1, x0:x1], comp[y0:y1, x0:x1]
        s = ssim(cv2.cvtColor(A, cv2.COLOR_BGR2GRAY), cv2.cvtColor(B, cv2.COLOR_BGR2GRAY), data_range=255)
        de = float(np.mean(deltaE_ciede2000(rgb2lab(A[..., ::-1] / 255.0), rgb2lab(B[..., ::-1] / 255.0))))
        res[f] = {'ssim': round(float(s), 4), 'de': round(de, 2), 'box': [x0, y0, x1, y1]}
        if sheet and (f - int(re.findall(r'(\d+)', os.path.basename(files[0]))[0])) % every == 0:
            d = cv2.applyColorMap(np.clip(cv2.absdiff(A, B).max(2).astype(np.int32) * 4, 0, 255).astype(np.uint8), cv2.COLORMAP_INFERNO)
            row = np.hstack([A, B, d]); h = 220; row = cv2.resize(row, (int(row.shape[1] * h / row.shape[0]), h))
            cv2.putText(row, f'{f}  ssim {s:.3f}  dE {de:.1f}', (6, 18), 0, 0.5, (0, 255, 0), 1, cv2.LINE_AA)
            rows.append(row)
    if sheet and rows:
        wmax = max(r.shape[1] for r in rows)
        cv2.imwrite(sheet, np.vstack([np.pad(r, ((0, 0), (0, wmax - r.shape[1]), (0, 0))) for r in rows]))
    v = [r['ssim'] for r in res.values()]
    print(f'objet : {len(v)} images, SSIM local moyen {np.mean(v):.4f} (min {min(v):.4f}), ΔE moyen {np.mean([r["de"] for r in res.values()]):.2f}')
    if rmcommon.arg(a, 'json', None):
        json.dump(res, open(rmcommon.arg(a, 'json'), 'w'))


if __name__ == '__main__':
    main()
