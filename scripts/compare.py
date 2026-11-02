"""Compare a reproduction with the original, frame by frame.

Usage: python3 compare.py <original.mp4> <copy.mp4> <start_s> <end_s> <out_dir> [--worst 6]
Writes out_dir/metrics.json (SSIM and mean Delta E 2000 per frame), a side-by-side
video (original | copy | differences) and stills of the worst frames.
"""
import sys, os, json, shutil, subprocess
import numpy as np
import cv2
from skimage.metrics import structural_similarity
from skimage.color import rgb2lab, deltaE_ciede2000


def frames(path, t0, t1, fps=None):
    cap = cv2.VideoCapture(path)
    fps = fps or cap.get(cv2.CAP_PROP_FPS)
    cap.set(cv2.CAP_PROP_POS_FRAMES, round(t0 * fps))
    for _ in range(round(t0 * fps), round(t1 * fps)):
        ok, img = cap.read()
        if not ok:
            return
        yield img


K5 = np.ones((7, 7), np.uint8)  # 3 px of tolerance: anti-aliased diagonals move by sub-pixel shifts


def _clustered(mask):
    m = cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    n, _, st, _ = cv2.connectedComponentsWithStats(m)
    return int(sum(st[i, 4] for i in range(1, n) if st[i, 4] >= 25))


def edge_diff(ga, gb):
    """(ghost_px, missing_px): clustered edges of the copy absent from the original (doubles, early/late
    elements) and edges of the original absent from the copy (a missing letter, a hole left in a plate)."""
    ea, eb = cv2.Canny(ga, 60, 160), cv2.Canny(gb, 60, 160)
    # the reference side uses a lower threshold: a faint edge just under the threshold in one video and just
    # over it in the other (low-contrast outline) is not a ghost
    la, lb = cv2.dilate(cv2.Canny(ga, 20, 60), K5), cv2.dilate(cv2.Canny(gb, 20, 60), K5)
    return (_clustered((eb > 0) & (la == 0)), _clustered((ea > 0) & (lb == 0)))


def ghost_px(ga, gb):
    """Edge pixels of the copy with no edge within 2 px in the original, kept only in clusters of 25+ px:
    doubled letters, a word shown too early, an element that should be hidden. Colour-blind, size-aware."""
    ea, eb = cv2.Canny(ga, 60, 160), cv2.Canny(gb, 60, 160)
    extra = ((eb > 0) & (cv2.dilate(ea, K5) == 0)).astype(np.uint8)
    extra = cv2.morphologyEx(extra, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    n, _, st, _ = cv2.connectedComponentsWithStats(extra)
    return int(sum(st[i, 4] for i in range(1, n) if st[i, 4] >= 25))


def main():
    orig, copy, t0, t1, out = sys.argv[1], sys.argv[2], float(sys.argv[3]), float(sys.argv[4]), sys.argv[5]
    worst_n = int(sys.argv[sys.argv.index('--worst') + 1]) if '--worst' in sys.argv else 6
    os.makedirs(out, exist_ok=True)
    rows, diffs = [], []
    side = os.path.join(out, 'side_frames'); shutil.rmtree(side, ignore_errors=True); os.makedirs(side)
    fps = cv2.VideoCapture(orig).get(cv2.CAP_PROP_FPS) or 30.0
    copy_iter = frames(copy, 0, t1 - t0, fps)
    for i, a in enumerate(frames(orig, t0, t1, fps)):
        b = next(copy_iter, None)
        if b is None:
            break
        if b.shape != a.shape:
            b = cv2.resize(b, (a.shape[1], a.shape[0]), interpolation=cv2.INTER_AREA)
        ga, gb = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY), cv2.cvtColor(b, cv2.COLOR_BGR2GRAY)
        ssim = structural_similarity(ga, gb, data_range=255)
        la = rgb2lab(a[::2, ::2, ::-1] / 255.0); lb = rgb2lab(b[::2, ::2, ::-1] / 255.0)
        de = deltaE_ciede2000(la, lb)
        diff = cv2.applyColorMap(np.clip(np.abs(a.astype(int) - b.astype(int)).sum(2) * 2, 0, 255).astype(np.uint8),
                                 cv2.COLORMAP_INFERNO)
        cv2.imwrite(os.path.join(side, f's_{i:05d}.png'), np.hstack([a, b, diff]))
        rows.append({'frame': i, 't': round(t0 + i / fps, 4), 'ssim': round(float(ssim), 4), **dict(zip(('ghost_px', 'missing_px'), edge_diff(ga, gb))),
                     'deltaE_mean': round(float(de.mean()), 3), 'deltaE_p95': round(float(np.percentile(de, 95)), 3)})
    worst = sorted(rows, key=lambda r: r['ssim'])[:worst_n]
    for r in worst:
        shutil.copyfile(os.path.join(side, f"s_{r['frame']:05d}.png"), os.path.join(out, f"worst_{r['frame']:05d}.png"))
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-framerate', f'{fps:g}', '-i', os.path.join(side, 's_%05d.png'),
                    '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-pix_fmt', 'yuv420p',
                    os.path.join(out, 'side_by_side.mp4')], check=True)
    if '--keep-frames' not in sys.argv:
        shutil.rmtree(side, ignore_errors=True)  # the worst frames are kept as stills; the rest is in the video
    ss = [r['ssim'] for r in rows]; de = [r['deltaE_mean'] for r in rows]
    summary = {'frames': len(rows), 'ssim_mean': round(float(np.mean(ss)), 4), 'ssim_min': round(float(np.min(ss)), 4),
               'share_ssim_ge_098': round(float(np.mean(np.array(ss) >= 0.98)), 3),
               'deltaE_mean': round(float(np.mean(de)), 3), 'worst_frames': [r['frame'] for r in worst]}
    summary['fps'] = fps
    json.dump({'summary': summary, 'rows': rows}, open(os.path.join(out, 'metrics.json'), 'w'), indent=1)
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
