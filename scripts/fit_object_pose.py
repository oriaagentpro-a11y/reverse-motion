"""3D pose of an object (icon, card, book, phone...) on every frame: homography + rotation + position.

Usage: python3 fit_object_pose.py <video> <out.json> --ref F --box x,y,w,h [--first F0] [--last F1]
                                  [--fov 30] [--depth 0.3] [--radius 0.22] [--min-cc 0.75] [--scale 0.5]
                                  [--sil light|dark|none] [--ignore x,y,w,h;...] [--smooth 1.5]
1. The object's region on the reference frame (`--box`, a clean frame where it is still and sharp) is aligned
   on every other frame with ECC (MOTION_HOMOGRAPHY), frame after frame, forward then backward, until the
   correlation falls under --min-cc (the object is gone, blurred, or hidden).
2. The four corners of the box are carried by the homography -> the object's FRONT FACE on each frame.
3. cv2.solvePnP on those corners (a square/rectangle of the box's proportions, camera of vertical field of view
   --fov, image centre as principal point) gives the 3D rotation and position: exactly what Three.js or
   Blender need to place a modelled object so that it covers the same pixels.
4. Tilted/turned square: IPPE gives TWO poses with the same corners. Both are refined (Powell) on the object's
   real silhouette (extruded rounded rectangle: --depth, --radius in face widths; mask --sil light/dark on the
   frame; --ignore boxes = parts stuck on the object such as a badge) and the one that covers the same pixels
   wins (P34). Frames where no silhouette is found (blur, fade) are dropped (the plate keeps them).
5. Rotation and position smoothed in time (gaussian, --smooth frames): measurement jitter = shading flicker.
Output: {"ref", "box", "fov", "w", "h", "frames": {f: {"H": [9], "quad": [[x,y]x4], "rot_deg": [rx, ry, rz],
         "pos": [x, y, z], "cc": .., "scale2d": .., "sil_iou": .., "rot_raw": [..]}}}  (rotation XYZ in degrees, OpenCV camera: x right, y down,
         z forward; blender_object.py and rm-3d.js convert to their own axes).
"""
import sys, os, json, math
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rmcommon  # noqa: E402


def main():
    a = sys.argv
    video, out = a[1], a[2]
    ref = rmcommon.arg(a, 'ref', None, int)
    bx, by, bw, bh = [float(v) for v in rmcommon.arg(a, 'box').split(',')]
    fov = rmcommon.arg(a, 'fov', 30.0, float); S = rmcommon.arg(a, 'scale', 0.5, float)
    min_cc = rmcommon.arg(a, 'min-cc', 0.75, float)
    V = rmcommon.probe(video)
    f0 = rmcommon.arg(a, 'first', 0, int); f1 = rmcommon.arg(a, 'last', V['frames'] - 1, int)
    cap = cv2.VideoCapture(video); cap.set(cv2.CAP_PROP_POS_FRAMES, f0); G = {}
    for f in range(f0, f1 + 1):
        ok, im = cap.read()
        if not ok:
            break
        g = cv2.resize(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY), None, fx=S, fy=S, interpolation=cv2.INTER_AREA).astype(np.float32)
        G[f] = cv2.GaussianBlur(g, (0, 0), 1.0)
    mask = np.zeros(G[ref].shape, np.uint8)
    pad = 0.08 * max(bw, bh)
    mask[int((by - pad) * S):int((by + bh + pad) * S), int((bx - pad) * S):int((bx + bw + pad) * S)] = 255
    crit = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 80, 1e-5)
    Hs, ccs = {ref: np.eye(3, dtype=np.float32)}, {ref: 1.0}
    for d in (1, -1):
        Hp = np.eye(3, dtype=np.float32); f = ref + d
        while f in G:
            try:
                cc, Hn = cv2.findTransformECC(G[ref], G[f], Hp.copy(), cv2.MOTION_HOMOGRAPHY, crit, mask, 5)
            except cv2.error:
                break
            if cc < min_cc:
                break
            Hs[f], ccs[f] = Hn, cc; Hp = Hn; f += d
    D = np.diag([1 / S, 1 / S, 1.0]); Di = np.linalg.inv(D)
    W, Hh = V['w'], V['h']
    fy = (Hh / 2) / math.tan(math.radians(fov) / 2)
    K = np.array([[fy, 0, W / 2], [0, fy, Hh / 2], [0, 0, 1]], np.float64)
    # object front face in its own units: width 1, height bh/bw, centred, z = 0
    ow, oh = 1.0, bh / bw
    obj = np.array([[-ow / 2, -oh / 2, 0], [ow / 2, -oh / 2, 0], [ow / 2, oh / 2, 0], [-ow / 2, oh / 2, 0]], np.float64)
    corners = np.array([[bx, by, 1], [bx + bw, by, 1], [bx + bw, by + bh, 1], [bx, by + bh, 1]], np.float64).T
    # --- silhouette refinement (P34): a planar square seen under a small tilt has TWO poses that give the same
    # four corners (IPPE ambiguity: tilted left/right, up/down). The object's thickness breaks the tie: the side
    # that shows is the side it is turned to. Both IPPE poses are refined on the object's real silhouette
    # (extruded rounded rectangle, depth --depth, corner radius --radius) and the better one is kept.
    sil = rmcommon.arg(a, 'sil', 'light')            # light | dark | none
    depth = rmcommon.arg(a, 'depth', 0.3, float); rad = rmcommon.arg(a, 'radius', 0.22, float)
    cap = cv2.VideoCapture(video)

    def outline(z, n=10):
        r = rad * ow; pts = []
        for cx, cy, a0 in ((ow / 2 - r, oh / 2 - r, 0), (-ow / 2 + r, oh / 2 - r, 90), (-ow / 2 + r, -oh / 2 + r, 180), (ow / 2 - r, -oh / 2 + r, 270)):
            for i in range(n + 1):
                t = math.radians(a0 + 90 * i / n); pts.append((cx + r * math.cos(t), cy + r * math.sin(t), z))
        return pts
    model = np.array(outline(0.0) + outline(depth), np.float64)

    def silhouette_mask(f):
        cap.set(cv2.CAP_PROP_POS_FRAMES, f); ok, im = cap.read()
        hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV)
        m = ((hsv[..., 1] < 90) & (hsv[..., 2] > 150)) if sil == 'light' else (hsv[..., 2] < 80)
        m = m.astype(np.uint8) * 255
        pad = int(0.6 * max(bw, bh)); x0, y0 = max(0, int(bx) - pad), max(0, int(by) - pad)
        roi = np.zeros_like(m); roi[y0:int(by + bh) + pad, x0:int(bx + bw) + pad] = 1; m *= roi
        n, lab, st, _ = cv2.connectedComponentsWithStats(m)
        if n < 2:
            return None
        k = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA])); m = (lab == k).astype(np.uint8)
        cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        out = np.zeros_like(m); cv2.drawContours(out, cs, -1, 1, -1)
        return out

    ign = [[float(v) for v in b.split(',')] for b in (rmcommon.arg(a, 'ignore', '') or '').split(';') if b]

    def ignore_mask(Hf, shape):
        # parts stuck on the object that are not the body (badge, sticker, hand): boxes given on the reference
        # frame, carried by the frame's homography, removed from both silhouettes
        z = np.ones(shape, np.uint8)
        for x, y, w_, h_ in ign:
            c = Hf @ np.array([[x, y, 1], [x + w_, y, 1], [x + w_, y + h_, 1], [x, y + h_, 1]], np.float64).T
            cv2.fillConvexPoly(z, (c[:2] / c[2]).T.astype(np.int32), 0)
        return z

    def iou(p, m):
        rv, tv = p[:3].reshape(3, 1), p[3:].reshape(3, 1)
        pr, _ = cv2.projectPoints(model, rv, tv, K, None)
        poly = np.zeros_like(m); cv2.fillConvexPoly(poly, cv2.convexHull(pr.reshape(-1, 2).astype(np.int32)), 1)
        poly &= IG
        inter = np.count_nonzero(poly & m); uni = np.count_nonzero(poly | m)
        return inter / max(uni, 1)

    def refine(p, m, q):
        from scipy.optimize import minimize
        sc = np.array([0.02, 0.02, 0.02, 0.01, 0.01, 0.1])
        def cost(u):
            pp = p + u * sc
            pr, _ = cv2.projectPoints(obj, pp[:3].reshape(3, 1), pp[3:].reshape(3, 1), K, None)
            reproj = np.mean(np.linalg.norm(pr.reshape(-1, 2) - q, axis=1)) / max(bw, 1)
            return (1 - iou(pp, m)) + 0.5 * reproj
        r = minimize(cost, np.zeros(6), method='Powell', options={'maxiter': 2500, 'xtol': 1e-3, 'ftol': 1e-5})
        return p + r.x * sc, 1 - r.fun
    res = {'ref': ref, 'box': [bx, by, bw, bh], 'fov': fov, 'w': W, 'h': Hh, 'depth': depth, 'radius': rad, 'frames': {}}
    prev = None
    for f in sorted(Hs, key=lambda k: abs(k - ref)):      # from the reference outwards: continuity tie-break
        Hf = D @ Hs[f].astype(np.float64) @ Di; Hf /= Hf[2, 2]
        q = Hf @ corners; q = (q[:2] / q[2]).T
        n_, rvs, tvs, _ = cv2.solvePnPGeneric(obj, q, K, None, flags=cv2.SOLVEPNP_IPPE)
        cands = [np.concatenate([r_.ravel(), t_.ravel()]) for r_, t_ in zip(rvs, tvs)]
        m = silhouette_mask(f) if sil != 'none' else None
        if m is not None:
            IG = ignore_mask(Hf, m.shape); m &= IG
        sil_iou = None
        if m is not None:
            scored = [refine(c, m, q) for c in cands]
            scored.sort(key=lambda s: -s[1]); best, sil_iou = scored[0]
            if len(scored) > 1 and scored[0][1] - scored[1][1] < 0.004 and prev is not None:   # tie: stay continuous
                best, sil_iou = min(scored, key=lambda s: np.linalg.norm(s[0][:3] - prev[:3]))
        else:
            best = cands[0] if prev is None else min(cands, key=lambda c: np.linalg.norm(c[:3] - prev[:3]))
        prev = best
        rv, tv = best[:3].reshape(3, 1), best[3:].reshape(3, 1)
        R, _ = cv2.Rodrigues(rv)
        # XYZ Euler (degrees) of R
        sy = math.hypot(R[0, 0], R[1, 0])
        rx, ry, rz = math.degrees(math.atan2(R[2, 1], R[2, 2])), math.degrees(math.atan2(-R[2, 0], sy)), math.degrees(math.atan2(R[1, 0], R[0, 0]))
        res['frames'][str(f)] = {'H': [round(float(v), 7) for v in Hf.ravel()], 'quad': [[round(float(x), 2), round(float(y), 2)] for x, y in q],
                                 'rot_deg': [round(rx, 3), round(ry, 3), round(rz, 3)], 'pos': [round(float(v), 5) for v in tv.ravel()],
                                 'cc': round(float(ccs[f]), 4), 'scale2d': round(float(math.sqrt(abs(np.linalg.det(Hf[:2, :2])))), 4),
                                 'sil_iou': None if sil_iou is None else round(float(sil_iou), 4)}
    res['frames'] = {k: res['frames'][k] for k in sorted(res['frames'], key=int)}
    bad = [k for k, v in res['frames'].items() if v['sil_iou'] is not None and v['sil_iou'] < 0.5]
    for k in bad:     # silhouette not found (blur, fade, cover): pose unreliable -> frame left to the plate
        del res['frames'][k]
    if bad:
        print('images sans silhouette fiable, retirées :', ', '.join(bad))
    sm = rmcommon.arg(a, 'smooth', 1.5, float)
    if sm > 0:   # temporal smoothing of rotation and position (measurement jitter = shading flicker in the render)
        ks = list(res['frames']); A = np.array([res['frames'][k]['rot_deg'] + res['frames'][k]['pos'] for k in ks])
        B = A.copy(); idx = np.arange(len(ks))
        for i in idx:
            wts = np.exp(-0.5 * ((idx - i) / sm) ** 2); wts /= wts.sum(); B[i] = wts @ A
        for k, b in zip(ks, B):
            res['frames'][k]['rot_raw'] = res['frames'][k]['rot_deg']
            res['frames'][k]['rot_deg'] = [round(float(v), 3) for v in b[:3]]; res['frames'][k]['pos'] = [round(float(v), 5) for v in b[3:]]
    json.dump(res, open(out, 'w'))
    ks = sorted(Hs)
    print(f'pose suivie sur {len(ks)} images ({ks[0]}-{ks[-1]}), corrélation min {min(ccs.values()):.3f} -> {out}')


if __name__ == '__main__':
    main()
