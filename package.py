"""Build the shareable zip: dist/reverse-motion.zip (no node_modules, no renders, no third-party video).
Usage: python3 package.py [out_dir]"""
import os, sys, zipfile, fnmatch
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'dist')
SKIP_DIRS = {'node_modules', '__pycache__', 'dist', '.git', 'vendor'}   # vendor: Three.js bundle, rebuilt by npm install
SKIP = ['examples/demo/out*', 'examples/demo/src/*.mp4', '*.pyc', '.DS_Store']
os.makedirs(OUT, exist_ok=True)
dst = os.path.join(OUT, 'reverse-motion.zip'); n = 0
with zipfile.ZipFile(dst, 'w', zipfile.ZIP_DEFLATED) as z:
    for root, dirs, files in os.walk(HERE):
        rel_root = os.path.relpath(root, HERE).replace(os.sep, '/')
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not any(fnmatch.fnmatch(f'{rel_root}/{d}'.lstrip('./'), p) for p in SKIP)]
        for f in files:
            rel = f'{rel_root}/{f}'.lstrip('./') if rel_root != '.' else f
            if any(fnmatch.fnmatch(rel, p) for p in SKIP):
                continue
            path = os.path.join(root, f)
            info = zipfile.ZipInfo.from_file(path, 'reverse-motion/' + rel)
            with open(path, 'rb') as fh:
                z.writestr(info, fh.read(), zipfile.ZIP_DEFLATED)
            n += 1
print(f'{n} fichiers -> {dst} ({os.path.getsize(dst) / 1e6:.1f} Mo)')
