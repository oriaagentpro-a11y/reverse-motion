"""Package fit_globe.py output for a scene: texture (data URL) + per-frame poses -> globe_data.js.

Usage: python3 globe_js.py <fit_dir> <out.js> [--tex-width 4096]
"""
import sys, os, json, base64
import cv2

d, out = sys.argv[1], sys.argv[2]
tw = int(sys.argv[sys.argv.index('--tex-width') + 1]) if '--tex-width' in sys.argv else 4096
g = json.load(open(os.path.join(d, 'globe_poses.json')))
tex = cv2.imread(os.path.join(d, g['texture']), cv2.IMREAD_GRAYSCALE)
if tex.shape[1] != tw:
    tex = cv2.resize(tex, (tw, tw // 2), interpolation=cv2.INTER_AREA)
ok, buf = cv2.imencode('.png', tex, [cv2.IMWRITE_PNG_COMPRESSION, 9])
data = {'texture': 'data:image/png;base64,' + base64.b64encode(buf.tobytes()).decode(), 'poses': g['poses']}
open(out, 'w').write('window.GLOBE = ' + json.dumps(data) + ';\n')
print(f"{len(g['poses'])} poses, texture {tex.shape[1]}x{tex.shape[0]} -> {out} [{os.path.getsize(out) / 1e6:.1f} MB]")
