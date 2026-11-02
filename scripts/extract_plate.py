"""Extract an "effect plate": a per-frame two-colour matte of an effect, measured on the original.

Why: some effects (zoomed pixel mosaics, liquid light, displaced ripples, soft waves) are
image processes whose exact shape cannot be retrieved as a formula. The plate keeps their shape
trait for trait while the colours stay editable (the WebGL layer maps the matte between any two
colours), and every element rebuilt in code (text, buttons, cursors) is removed from the plate.

Usage:
  python3 extract_plate.py <video> <start_s> <end_s> <colorA> <colorB> <out.js> <name>
         [--holes holes.json] [--open K] [--close K] [--snap 0.03] [--scale 1]
colorA / colorB: hex colours of the two ends (A = alpha 0, B = alpha 1), e.g. 5000B0 FFFFFF.
holes.json: [{"t0": 2.6, "t1": 3.0, "rect": [x, y, w, h]}, ...] areas holding rebuilt elements;
            they are filled by inpainting from the surrounding effect.
--open K / --close K: grey-level opening / closing (kernel K px) to wipe thin strokes left in the
            matte (open removes thin light strokes, close removes thin dark strokes).
--holes-from DIR:FIRST_FRAME:DILATE  RGBA frames of the rebuilt foreground (render.mjs --transparent);
            every pixel they cover (dilated by DILATE px) becomes a hole. FIRST_FRAME = global index of f_00000.png.
--holes-ink COLOR:TOL:RADIUS  (repeatable) also punch the ORIGINAL pixels of that ink colour (within TOL)
            lying within RADIUS px of a rebuilt element: no ghost of the original text can survive in the plate,
            even where the rebuilt text is slightly off.
--third CCCCCC  three-colour plate: each pixel = A + wB (B - A) + wC (C - A) (least squares, clipped);
            wB, wC stored in the R and G channels. For off-line tints (lavender balls, glows, flashes).
--rgb [Q]   TRUE-COLOUR plate: the original frame itself (holes inpainted), stored as WebP quality Q (default 95).
            For videos whose effects are not two or three flat colours (glass, glows, gradients, 3D renders).
            colorA / colorB are then ignored (pass - -). The plate is drawn as is (no colour remap).
--snap S:   alpha below S becomes 0 and above 1-S becomes 1 (removes compression noise on flats).
Output: a JS file  window.PLATES = window.PLATES || {}; window.PLATES[name] = {a, b, w, h, frames: {frame: dataURL}}
"""
import sys, json, base64
import numpy as np
import cv2


def hex2rgb(h):
    h = h.lstrip('#'); return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], np.float32)


def main():
    a = sys.argv
    video, t0, t1, ca, cb, out, name = a[1], float(a[2]), float(a[3]), a[4], a[5], a[6], a[7]
    opt = lambda k, d: a[a.index(k) + 1] if k in a else d
    holes = json.load(open(opt('--holes', ''))) if '--holes' in a else []
    k_open, k_close = int(opt('--open', 0)), int(opt('--close', 0))
    hfs = [a[i + 1] for i, x in enumerate(a) if x == '--holes-from']   # may be repeated (several rebuilt layers)
    hsrc = []
    for hf in hfs:
        hdir, hfirst, hdil = hf.rsplit(':', 2)
        hsrc.append((hdir, int(hfirst), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * int(hdil) + 1, 2 * int(hdil) + 1))))
    snap, scale = float(opt('--snap', 0.03)), float(opt('--scale', 1))
    hinks = []
    for i, x in enumerate(a):
        if x == '--holes-ink':
            c, t_, r_ = a[i + 1].split(':'); hinks.append((np.array([int(c[k:k + 2], 16) for k in (4, 2, 0)], np.float32), float(t_), int(r_)))
    A, B = (hex2rgb(ca), hex2rgb(cb)) if '--rgb' not in a else (np.zeros(3, np.float32), np.ones(3, np.float32))
    D = B - A; dd = float(D @ D)
    third = opt('--third', None)
    rgbq = None
    if '--rgb' in a:
        nxt = a[a.index('--rgb') + 1] if a.index('--rgb') + 1 < len(a) else ''
        rgbq = int(nxt) if nxt.isdigit() else 95
    if third:
        Cc = hex2rgb(third); M = np.stack([B - A, Cc - A], 1)          # 3x2
        Minv = np.linalg.pinv(M)                                        # 2x3 least-squares solver
    cap = cv2.VideoCapture(video); fps = cap.get(cv2.CAP_PROP_FPS)
    f0, f1 = round(t0 * fps), round(t1 * fps)
    cap.set(cv2.CAP_PROP_POS_FRAMES, f0)
    frames = {}
    for f in range(f0, f1):
        ok, img = cap.read()
        if not ok:
            break
        rgb = img[:, :, ::-1].astype(np.float32)
        if rgbq:
            m8 = img.copy()                                              # BGR, kept as is
        elif third:
            w = (rgb - A) @ Minv.T                                       # H x W x 2
            w = np.clip(w, 0, 1); ssum = w.sum(2, keepdims=True); w = np.where(ssum > 1, w / ssum, w)
            m8 = np.dstack([w[..., 0], w[..., 1], np.zeros_like(w[..., 0])])
            m8 = (m8 * 255 + 0.5).astype(np.uint8)
        else:
            al = np.clip(((rgb - A) @ D) / dd, 0, 1)
            m8 = (al * 255 + 0.5).astype(np.uint8)
        if k_open:
            m8 = cv2.morphologyEx(m8, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k_open, k_open)))
        if k_close:
            m8 = cv2.morphologyEx(m8, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k_close, k_close)))
        t = f / fps
        hm = np.zeros(m8.shape[:2], np.uint8)
        for h in holes:
            if h['t0'] - 1e-6 <= t <= h['t1'] + 1e-6:
                x, y, w, hh = h['rect']; hm[max(0, y):y + hh, max(0, x):x + w] = 255
        fgall = np.zeros(m8.shape[:2], np.uint8)
        for hdir, hfirst, hker in hsrc:
            import os
            pth = os.path.join(hdir, f'f_{f - hfirst:05d}.png')
            if os.path.exists(pth):
                fg = cv2.imread(pth, cv2.IMREAD_UNCHANGED)
                if fg is None or fg.ndim < 3 or fg.shape[2] != 4:
                    sys.exit(f'ERREUR: {pth} n\'a pas de canal alpha (page non transparente ?) : aucun trou ne serait percé.')
                if True:
                    fgm = (fg[:, :, 3] > 8).astype(np.uint8) * 255
                    fgall = np.maximum(fgall, fgm)
                    hm = np.maximum(hm, cv2.dilate(fgm, hker))
        for IC, itol, irad in hinks:
            if fgall.any():
                near = cv2.dilate(fgall, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * irad + 1, 2 * irad + 1)))
                inkpx = (np.linalg.norm(img.astype(np.float32) - IC, axis=2) < itol).astype(np.uint8) * 255
                hm = np.maximum(hm, cv2.dilate(cv2.bitwise_and(near, inkpx), np.ones((11, 11), np.uint8)))
        if hm.any():
            m8 = cv2.inpaint(m8, hm, 6, cv2.INPAINT_TELEA)
        if not rgbq:
            s = snap * 255
            m8 = np.where(m8 < s, 0, np.where(m8 > 255 - s, 255, m8)).astype(np.uint8)
        if third:
            m8 = m8[:, :, ::-1]                                          # RGB order for the PNG (OpenCV writes BGR)
        if scale != 1:
            m8 = cv2.resize(m8, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        if rgbq:
            ok, buf = cv2.imencode('.webp', m8, [cv2.IMWRITE_WEBP_QUALITY, rgbq])
            frames[f] = 'data:image/webp;base64,' + base64.b64encode(buf.tobytes()).decode()
        else:
            ok, buf = cv2.imencode('.png', m8, [cv2.IMWRITE_PNG_COMPRESSION, 9])
            frames[f] = 'data:image/png;base64,' + base64.b64encode(buf.tobytes()).decode()
    data = {'rgb': bool(rgbq), 'a': '#' + ca.lstrip('#'), 'b': '#' + cb.lstrip('#'), 'c': ('#' + third.lstrip('#')) if third else None, 'w': int(img.shape[1] * scale), 'h': int(img.shape[0] * scale), 'frames': frames}
    with open(out, 'w') as fh:
        # first line = the exact command, so a plate can always be re-extracted with the same options
        fh.write('// extract_plate.py ' + ' '.join(a[1:]) + '\n')
        fh.write('window.PLATES = window.PLATES || {};\nwindow.PLATES[' + json.dumps(name) + '] = ' + json.dumps(data) + ';\n')
    size = sum(len(v) for v in frames.values()) / 1e6
    print(f'{len(frames)} plate frames ({f0}-{f1 - 1}) -> {out}  [{size:.1f} MB]')


if __name__ == '__main__':
    main()
