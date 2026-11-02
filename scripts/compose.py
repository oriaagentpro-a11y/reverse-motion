"""Stack rendered layers into one video segment (alpha compositing, bottom to top).

Usage: python3 compose.py <out.mp4> <start_s> <end_s> <layer> [<layer> ...] [--audio src.mp4] [--fps 30]
layer = "path:start_s" where path is an .mp4 (opaque) or a folder of RGBA PNG frames (f_00000.png...),
and start_s is the global time of the layer's first frame. Frames outside a layer's range are skipped.
"""
import sys, os, glob, shutil, subprocess
import numpy as np
FPS = 30.0
import cv2


class Layer:
    def __init__(self, spec):
        path, start = spec.rsplit(':', 1)
        self.start = float(start); self.path = path
        if os.path.isdir(path):
            self.files = sorted(glob.glob(os.path.join(path, 'f_*.png'))); self.cap = None; self.n = len(self.files)
        else:
            self.cap = cv2.VideoCapture(path); self.n = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT)); self.pos = -1

    def get(self, f):  # f = global frame index
        i = f - round(self.start * FPS)
        if i < 0 or i >= self.n:
            return None
        if self.cap is None:
            img = cv2.imread(self.files[i], cv2.IMREAD_UNCHANGED)
            return img if img.shape[2] == 4 else np.dstack([img, np.full(img.shape[:2], 255, np.uint8)])
        if i != self.pos + 1:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ok, img = self.cap.read(); self.pos = i
        return np.dstack([img, np.full(img.shape[:2], 255, np.uint8)]) if ok else None


def main():
    a = [x for x in sys.argv[1:]]
    global FPS
    opts = {}
    for k in ('--audio', '--fps'):
        if k in a:
            i = a.index(k); opts[k] = a[i + 1]; del a[i:i + 2]
    audio = opts.get('--audio'); FPS = float(opts.get('--fps', 30))
    out, t0, t1 = a[0], float(a[1]), float(a[2])
    layers = [Layer(s) for s in a[3:]]
    tmp = out + '_frames'; shutil.rmtree(tmp, ignore_errors=True); os.makedirs(tmp)
    size = None
    for k, f in enumerate(range(round(t0 * FPS), round(t1 * FPS))):
        imgs = [(L, L.get(f)) for L in layers]
        if size is None:  # frame size = first layer that has a frame (no hard-coded resolution)
            size = next((im.shape[:2] for _, im in imgs if im is not None), None)
        acc = np.zeros((*(size or (2, 2)), 3), np.float32)
        for L, img in imgs:
            if img is None:
                continue
            if img.shape[:2] != acc.shape[:2]:
                img = cv2.resize(img, (acc.shape[1], acc.shape[0]), interpolation=cv2.INTER_AREA)
            al = img[:, :, 3:4].astype(np.float32) / 255
            acc = acc * (1 - al) + img[:, :, :3].astype(np.float32) * al
        cv2.imwrite(os.path.join(tmp, f'f_{k:05d}.png'), np.clip(acc + 0.5, 0, 255).astype(np.uint8))
    cmd = ['ffmpeg', '-y', '-v', 'error', '-framerate', f'{FPS:g}', '-i', os.path.join(tmp, 'f_%05d.png')]
    if audio:
        cmd += ['-ss', str(t0), '-t', str(t1 - t0), '-i', audio, '-map', '0:v', '-map', '1:a', '-c:a', 'aac', '-shortest']
    cmd += ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '12', '-pix_fmt', 'yuv420p', out]
    subprocess.run(cmd, check=True)
    shutil.rmtree(tmp, ignore_errors=True)  # long videos: do not leave thousands of PNGs behind
    print(f'composed {round((t1 - t0) * FPS)} frames -> {out}')


if __name__ == '__main__':
    main()
