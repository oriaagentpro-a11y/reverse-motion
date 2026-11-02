"""Recover the exact pose of a rotating globe on every frame (orthographic projection).

1. Rasterises a world map (TopoJSON land, world-atlas) into an equirectangular texture.
2. For each frame, renders the globe with a camera (lon0, lat0, roll, radius, cx, cy) and minimises
   the difference with the land mask seen in the original (Nelder-Mead, started from the previous
   frame; first frame from a coarse grid). Soft masks keep the objective smooth.
3. Writes the per-frame poses + the texture. The scene's WebGL shader uses the very same formula,
   so what was measured is exactly what is drawn.

Usage: python3 fit_globe.py <video> <f0> <f1> <land.json> <out_dir> --land-color 5000B0 --bg-color FFFFFF
        [--init lon,lat,roll,r,cx,cy] [--mask-out x,y,w,h ...] [--tex 4096]
Perspective: pose may carry a 7th value, the camera distance in sphere radii (After Effects-like 3D camera).
Camera: c = Rz(roll) . Rx(lat0) . Ry(-lon0) . w ; screen x = cx + r*c.x, y = cy - r*c.y, visible if c.z > 0
with w(lon, lat) = (cos(lat) sin(lon), sin(lat), cos(lat) cos(lon)).
"""
import sys, os, json, math
import numpy as np
import cv2
from scipy.optimize import minimize


def topo_rings(path, obj='land'):
    t = json.load(open(path))
    sc, tr = t['transform']['scale'], t['transform']['translate']
    arcs = []
    for a in t['arcs']:
        x = y = 0; pts = []
        for dx, dy in a:
            x += dx; y += dy; pts.append((x * sc[0] + tr[0], y * sc[1] + tr[1]))
        arcs.append(pts)

    def ring(idx):
        out = []
        for i in idx:
            pts = arcs[i] if i >= 0 else arcs[~i][::-1]
            out.extend(pts if not out else pts[1:])
        return out
    polys = []
    geoms = t['objects'][obj]['geometries'] if t['objects'][obj]['type'] == 'GeometryCollection' else [t['objects'][obj]]
    for g in geoms:
        if g['type'] == 'Polygon':
            polys.append([ring(r) for r in g['arcs']])
        elif g['type'] == 'MultiPolygon':
            polys += [[ring(r) for r in p] for p in g['arcs']]
    return polys


def land_texture(path, W):
    H = W // 2
    tex = np.zeros((H, W), np.uint8)
    for poly in topo_rings(path):
        rings = []
        for r in poly:
            lon = np.array([p[0] for p in r]); lat = np.array([p[1] for p in r])
            lon = np.degrees(np.unwrap(np.radians(lon)))         # continuous across the antimeridian
            if abs(lon[-1] - lon[0]) > 300:                        # ring around a pole (Antarctica): close via the pole
                pole = -90 if lat.mean() < 0 else 90
                lon = np.r_[lon, lon[-1], lon[0]]; lat = np.r_[lat, pole, pole]
            rings.append((lon, lat))
        for off in (-360, 0, 360):
            pts = [np.stack([(l + off + 180) / 360 * W, (90 - la) / 180 * H], 1).round().astype(np.int32) for l, la in rings]
            cv2.fillPoly(tex, pts, 255, lineType=cv2.LINE_AA)
    return tex


def rot(lon0, lat0, roll):
    a, b, c = math.radians(-lon0), math.radians(lat0), math.radians(roll)
    Ry = np.array([[math.cos(a), 0, math.sin(a)], [0, 1, 0], [-math.sin(a), 0, math.cos(a)]])
    Rx = np.array([[1, 0, 0], [0, math.cos(b), -math.sin(b)], [0, math.sin(b), math.cos(b)]])
    Rz = np.array([[math.cos(c), -math.sin(c), 0], [math.sin(c), math.cos(c), 0], [0, 0, 1]])
    return Rz @ Rx @ Ry


def render(tex, pose, W, H, scale=1.0):
    # pose = lon0, lat0, roll, r, cx, cy[, dist]  -- dist = camera distance in sphere radii (perspective);
    # absent or >= 1e3 -> orthographic. r = pixels per sphere radius on the plane through the sphere centre.
    lon0, lat0, roll, r, cx, cy = pose[:6]
    dist = pose[6] if len(pose) > 6 else 1e4
    ys, xs = np.mgrid[0:H, 0:W].astype(np.float32)
    u = (xs / scale - cx) / r; v = (ys / scale - cy) / r
    if dist >= 1e3:
        d = u * u + v * v; inside = d < 1
        C = np.stack([u, -v, np.sqrt(np.clip(1 - d, 0, 1))], -1)
    else:  # ray from the camera (0,0,dist) through the image point (u,-v,0), first hit on the unit sphere
        dd = dist * dist; n2 = u * u + v * v + dd
        disc = dd * dd - n2 * (dd - 1); inside = disc > 0
        t = (dd - np.sqrt(np.clip(disc, 0, None))) / n2
        C = np.stack([t * u, -t * v, dist - t * dist], -1)
    Wd = C @ rot(lon0, lat0, roll)            # inverse rotation (orthonormal): w = R^T c  ->  c @ R
    lat = np.arcsin(np.clip(Wd[..., 1], -1, 1)); lon = np.arctan2(Wd[..., 0], Wd[..., 2])
    th, tw = tex.shape
    tx = ((lon + np.pi) / (2 * np.pi) * tw).astype(np.float32); ty = ((np.pi / 2 - lat) / np.pi * th).astype(np.float32)
    val = cv2.remap(tex, tx, ty, cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP).astype(np.float32) / 255
    return np.where(inside, val, 0)


PC = (368.0, 207.0)   # principal point = image centre (After Effects camera)


def render_offaxis(tex, pose, W, H, scale=1.0, pc=PC):
    # True 3D scene: camera at the origin looking along -z, focal f (pixels), principal point = image centre;
    # unit sphere centred at (X, Y, -Z). pose = lon0, lat0, roll, X, Y, Z, f. Off-axis spheres project as
    # ellipses with their own perspective -> this is what a centred-camera model cannot reproduce.
    lon0, lat0, roll, X, Y, Z, f = pose
    ys, xs = np.mgrid[0:H, 0:W].astype(np.float32)
    dx = (xs / scale - pc[0]) / f; dy = -(ys / scale - pc[1]) / f; dz = -np.ones_like(dx)
    S = np.array([X, Y, -Z], np.float32)
    dS = dx * S[0] + dy * S[1] + dz * S[2]; dd = dx * dx + dy * dy + 1.0
    disc = dS * dS - dd * (float(S @ S) - 1.0); inside = disc > 0
    t = (dS - np.sqrt(np.clip(disc, 0, None))) / dd
    C = np.stack([t * dx - S[0], t * dy - S[1], t * dz - S[2]], -1)
    Wd = C @ rot(lon0, lat0, roll)
    lat = np.arcsin(np.clip(Wd[..., 1], -1, 1)); lon = np.arctan2(Wd[..., 0], Wd[..., 2])
    th, tw = tex.shape
    tx = ((lon + np.pi) / (2 * np.pi) * tw).astype(np.float32); ty = ((np.pi / 2 - lat) / np.pi * th).astype(np.float32)
    val = cv2.remap(tex, tx, ty, cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP).astype(np.float32) / 255
    return np.where(inside, val, 0)


def render_radial(tex, pose, W, H, scale=1.0):
    # "Spherize"-type globe (2D map wrapped radially, as done by distortion effects):
    # pose = lon0, lat0, roll, r, cx, cy, tmax (deg, visible angle at the rim), beta (0 = orthographic
    # profile sin, 1 = equidistant profile), asp (vertical squash). tmax=90, beta=0, asp=1 -> orthographic.
    lon0, lat0, roll, r, cx, cy, tmax, beta, asp = pose
    ys, xs = np.mgrid[0:H, 0:W].astype(np.float32)
    u = (xs / scale - cx) / r; v = (ys / scale - cy) / (r * asp)
    rho = np.sqrt(u * u + v * v); inside = rho < 1
    rc = np.clip(rho, 0, 1)
    prof = (1 - beta) * (np.arcsin(rc) / (np.pi / 2)) + beta * rc
    th = np.radians(tmax) * prof
    k = np.where(rho > 1e-6, np.sin(th) / np.maximum(rho, 1e-6), 1.0)
    C = np.stack([u * k, -v * k, np.cos(th)], -1)
    Wd = C @ rot(lon0, lat0, roll)
    lat = np.arcsin(np.clip(Wd[..., 1], -1, 1)); lon = np.arctan2(Wd[..., 0], Wd[..., 2])
    th_, tw = tex.shape
    tx = ((lon + np.pi) / (2 * np.pi) * tw).astype(np.float32); ty = ((np.pi / 2 - lat) / np.pi * th_).astype(np.float32)
    val = cv2.remap(tex, tx, ty, cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP).astype(np.float32) / 255
    return np.where(inside, val, 0)


def centred_to_offaxis(p):
    lon0, lat0, roll, r, cx, cy = p[:6]; dist = p[6] if len(p) > 6 else 50.0
    f = r * dist
    return [lon0, lat0, roll, (cx - PC[0]) / r, -(cy - PC[1]) / r, dist, f]


def main():
    a = sys.argv
    video, f0, f1, land, out = a[1], int(a[2]), int(a[3]), a[4], a[5]
    opt = lambda k, d: a[a.index(k) + 1] if k in a else d
    LC = np.array([int(opt('--land-color', '5000B0')[i:i + 2], 16) for i in (4, 2, 0)], np.float32)
    BC = np.array([int(opt('--bg-color', 'FFFFFF')[i:i + 2], 16) for i in (4, 2, 0)], np.float32)
    TW = int(opt('--tex', 4096))
    masks_out = [list(map(int, a[i + 1].split(','))) for i, x in enumerate(a) if x == '--mask-out']
    os.makedirs(out, exist_ok=True)
    tex = land_texture(land, TW)
    cv2.imwrite(os.path.join(out, 'land_equirect.png'), tex)
    S = 0.5                                              # fit at half resolution
    cap = cv2.VideoCapture(video)
    poses = {}
    pose = list(map(float, opt('--init', '-100,40,0,250,388,300').split(',')))
    for f in range(f0, f1 + 1):
        cap.set(cv2.CAP_PROP_POS_FRAMES, f); ok, img = cap.read()
        if not ok:
            break
        D = LC - BC
        al = np.clip(((img.astype(np.float32) - BC) @ D) / (D @ D), 0, 1)
        weight = np.ones_like(al)
        for x, y, w, h in masks_out:
            weight[y:y + h, x:x + w] = 0
        al = cv2.resize(al, None, fx=S, fy=S, interpolation=cv2.INTER_AREA)
        weight = cv2.resize(weight, None, fx=S, fy=S, interpolation=cv2.INTER_AREA)
        H, W = al.shape
        tgt = cv2.GaussianBlur(al, (0, 0), 1.5)

        def loss(p, blur=1.5):
            if p[3] < 30 or (len(p) > 6 and p[6] < 1.05):
                return 1e9
            m = cv2.GaussianBlur(render(tex, p, W, H, S), (0, 0), blur)
            return float((np.abs(m - tgt) * weight).sum() / weight.sum())
        if f == f0 and '--init' not in a:  # coarse grid on orientation AND size/position (quarter resolution), best candidates refined
            q = 0.25; Hq, Wq = int(H / S * q), int(W / S * q)
            tq = cv2.resize(tgt, (Wq, Hq), interpolation=cv2.INTER_AREA); wq = cv2.resize(weight, (Wq, Hq), interpolation=cv2.INTER_AREA)
            texq = cv2.resize(tex, (1024, 512), interpolation=cv2.INTER_AREA)
            cands = []
            for r in range(200, 381, 30):
                for cx in range(300, 461, 40):
                    for cy in range(220, 421, 40):
                        for lon in range(-180, 180, 15):
                            for lat in range(-45, 76, 15):
                                pp = [lon, lat, 0, r, cx, cy]
                                m = render(texq, pp, Wq, Hq, q)
                                cands.append((float((np.abs(m - tq) * wq).sum() / wq.sum()), pp))
            cands.sort(key=lambda c: c[0])
            best = None
            for _, pp in cands[:6]:
                rr = minimize(loss, pp, method='Nelder-Mead', options={'initial_simplex': [pp] + [list(np.array(pp) + np.eye(6)[i] * [10, 8, 8, 25, 20, 20][i]) for i in range(6)], 'maxiter': 700})
                if best is None or rr.fun < best[0]:
                    best = (rr.fun, list(rr.x))
            pose = best[1]
            print('grid start', [round(v, 2) for v in pose], round(best[0], 4), flush=True)
        if len(pose) < 7:
            pose = pose + [float(opt('--dist', 3.0))]
        steps = [8, 6, 6, 20, 15, 15, 0.5]
        res = minimize(loss, pose, method='Nelder-Mead',
                       options={'initial_simplex': [pose] + [list(np.array(pose) + np.eye(7)[i] * steps[i]) for i in range(7)],
                                'xatol': 0.02, 'fatol': 1e-6, 'maxiter': 900})
        pose = list(res.x)
        res2 = minimize(loss, pose, method='Nelder-Mead',
                        options={'initial_simplex': [pose] + [list(np.array(pose) + np.eye(7)[i] * np.array([1, 1, 1, 3, 2, 2, 0.1])[i]) for i in range(7)],
                                 'xatol': 0.005, 'fatol': 1e-7, 'maxiter': 600})
        if res2.fun < res.fun:
            pose = list(res2.x)
        poses[f] = [round(v, 4) for v in pose]
        print(f'frame {f}: pose {poses[f]}  err {min(res.fun, res2.fun):.4f}', flush=True)
    json.dump({'texture': 'land_equirect.png', 'poses': poses}, open(os.path.join(out, 'globe_poses.json'), 'w'))
    print('->', out)


if __name__ == '__main__':
    main()
