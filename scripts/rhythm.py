"""Check that two videos share the same rhythm (a rebrand must keep every movement on the same frame).

Usage: python3 rhythm.py <original.mp4> <other.mp4> <out.json> [--start 0] [--end END]
Colours differ in a rebrand, so pixels are not compared. What is compared is WHEN things move:
- motion curve = per-frame amount of change (edges of frame n vs frame n-1, colour-blind);
- correlation of the two curves at lags -5..+5 frames (best lag must be 0);
- events = peaks of the curve (cuts, entrances, impacts); each original event is matched to the nearest
  event of the other video and the offset in frames is reported.
Verdict "identique" when the best lag is 0 and either the curves correlate at >= 0.95, or at least 90 % of the
events are matched at 0 or +-1 frame (a changed text or logo adds or removes a few edge events of its own).
"""
import sys, os, json, subprocess
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rmcommon  # noqa: E402


def motion(path, f0, f1, size=(184, 104)):
    V = rmcommon.probe(path)
    dec = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', path, '-vf', f"select='between(n\\,{f0}\\,{f1 - 1})',scale={size[0]}:{size[1]}",
                            '-vsync', '0', '-f', 'rawvideo', '-pix_fmt', 'gray', '-'], stdout=subprocess.PIPE)
    prev, cur = None, []
    while True:
        b = dec.stdout.read(size[0] * size[1])
        if len(b) < size[0] * size[1]:
            break
        g = np.frombuffer(b, np.uint8).reshape(size[1], size[0])
        e = cv2.Canny(g, 40, 120).astype(np.float32) / 255  # edges: shapes and text, whatever their colour
        e = cv2.GaussianBlur(e, (0, 0), 1.2)
        cur.append(0.0 if prev is None else float(np.abs(e - prev).mean())); prev = e
    dec.wait()
    return np.array(cur), V['fps']


def peaks(c, rel=0.25):
    thr = rel * np.percentile(c, 99)
    return [i for i in range(2, len(c) - 2) if c[i] >= thr and c[i] == c[i - 2:i + 3].max()]


def main():
    a = sys.argv
    o, x, out = a[1], a[2], a[3]
    V = rmcommon.probe(o)
    t0 = rmcommon.arg(a, 'start', 0.0, float); t1 = rmcommon.arg(a, 'end', V['frames'] / V['fps'], float)
    f0, f1 = round(t0 * V['fps']), round(t1 * V['fps'])
    co, fps = motion(o, f0, f1); cx, _ = motion(x, f0, f1)
    n = min(len(co), len(cx)); co, cx = co[:n], cx[:n]
    z = lambda v: (v - v.mean()) / (v.std() + 1e-9)
    corr = {L: float(np.mean(z(co)[max(0, L):n + min(0, L)] * z(cx)[max(0, -L):n - max(0, L)])) for L in range(-5, 6)}
    best = max(corr, key=corr.get)
    po, px = peaks(co), peaks(cx)
    ev = []
    for p in po:
        q = min(px, key=lambda q: abs(q - p)) if px else None
        ev.append({'frame': f0 + p, 't': round((f0 + p) / fps, 3), 'offset': None if q is None or abs(q - p) > 6 else q - p})
    ok = [e for e in ev if e['offset'] is not None and abs(e['offset']) <= 1]
    exact = [e for e in ev if e['offset'] == 0]
    res = {'frames': n, 'fps': fps, 'best_lag': best, 'corr_at_0': round(corr[0], 4), 'corr_by_lag': {k: round(v, 4) for k, v in corr.items()},
           'events': len(ev), 'events_exact': len(exact), 'events_within_1': len(ok),
           'share_within_1': round(len(ok) / max(1, len(ev)), 3),
           'off_events': [e for e in ev if e not in ok]}
    # the curve correlation is the robust test; peak matching is noisy where many small peaks are close together
    res['verdict'] = 'identique' if best == 0 and (res['corr_at_0'] >= 0.95 or res['share_within_1'] >= 0.90) else 'à vérifier'
    json.dump(res, open(out, 'w'), indent=1)
    print(f"rythme : décalage optimal {best} image(s), corrélation {res['corr_at_0']}, "
          f"{len(exact)}/{len(ev)} événements à l'image près, {len(ok)}/{len(ev)} à ±1 image -> {res['verdict']}")


if __name__ == '__main__':
    main()
