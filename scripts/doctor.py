"""Check that everything reverse-motion needs is installed, then render a 1-second test scene.

Usage: python3 doctor.py [--no-render]
Prints one line per requirement (OK / MANQUANT and how to fix it). Exit code 1 if something is missing.
"""
import sys, os, shutil, subprocess, importlib, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import rmcommon  # noqa: E402

ok = True


def line(good, what, fix=''):
    global ok
    ok &= good
    print(f"  {'OK      ' if good else 'MANQUANT'}  {what}" + ('' if good else f'  ->  {fix}'))


print('reverse-motion : vérification de l\'installation')
line(sys.version_info >= (3, 9), f'Python {sys.version.split()[0]}', 'Python 3.9 ou plus récent')
for exe, fix in [('node', 'Node.js 18+ : https://nodejs.org'), ('ffmpeg', 'brew/apt/winget install ffmpeg'),
                 ('ffprobe', 'fourni avec ffmpeg'),
                 ('tesseract', 'OCR : brew install tesseract tesseract-lang | sudo apt install tesseract-ocr tesseract-ocr-fra | winget install UB-Mannheim.TesseractOCR')]:
    line(shutil.which(exe) is not None, exe, fix)
for mod, pkg in [('numpy', 'numpy'), ('cv2', 'opencv-python'), ('skimage', 'scikit-image'), ('scipy', 'scipy'),
                 ('PIL', 'pillow'), ('playwright', 'playwright'), ('librosa', 'librosa'), ('fontTools', 'fonttools'), ('pytesseract', 'pytesseract')]:
    try:
        importlib.import_module(mod); good = True
    except Exception:  # noqa: BLE001
        good = False
    line(good, f'module Python {pkg}', f'pip install -r {os.path.join(ROOT, "requirements.txt")}')
nm = os.path.join(ROOT, 'engine', 'node_modules')
for pkg in ['playwright', 'gsap', 'pngjs', 'd3-geo', 'topojson-client', 'world-atlas']:
    line(os.path.isdir(os.path.join(nm, pkg)), f'module Node {pkg}', f'cd {os.path.join(ROOT, "engine")} && npm install')
# 3D objects (rule "objets 3D"): Three.js bundle for live models, Blender (bpy module or executable) for Cycles renders
line(os.path.isfile(os.path.join(ROOT, 'engine', 'vendor', 'three-rm.js')), 'Three.js (engine/vendor/three-rm.js)',
     f'cd {os.path.join(ROOT, "engine")} && npm install   (construit le bundle)')
try:
    import bpy  # noqa: F401
    line(True, f'Blender (module bpy {bpy.app.version_string})')
except Exception:  # noqa: BLE001
    bl = os.environ.get('BLENDER_PATH') or shutil.which('blender')
    line(bl is not None, f'Blender ({bl or "introuvable"})', f'bash {os.path.join(HERE, "blender_setup.sh")}')
exe = rmcommon.chrome_path()
line(exe is not None, f'Chromium ({exe or "introuvable"})', 'cd engine && npx playwright install chromium   (ou CHROME_PATH=...)')

if ok and '--no-render' not in sys.argv:
    tmp = tempfile.mkdtemp(prefix='rm-doctor-')
    scene = os.path.join(tmp, 'test.html')
    eng = os.path.join(ROOT, 'engine').replace(os.sep, '/')
    open(scene, 'w').write(f'''<!doctype html><html><head><meta charset="utf-8"><style>
@font-face {{ font-family: 'RM'; src: url('file:///{eng.lstrip('/')}/Outfit-var.ttf'); font-weight: 100 900; }}
html,body{{margin:0;background:#fff}} svg text{{font-family:'RM'}}</style></head><body>
<svg width="320" height="180"><rect id="r" x="20" y="60" width="60" height="60" rx="12" fill="#5000B0"/><text id="t" fill="#5000B0">Bonjour</text></svg>
<script src="file:///{eng.lstrip('/')}/node_modules/gsap/dist/gsap.min.js"></script><script src="file:///{eng.lstrip('/')}/rm.js"></script>
<script>(async () => {{ await RM.fontsReady(); RM.fitInk(document.getElementById('t'), {{ left: 110, top: 70, w: 150, wt: 700 }});
const tl = gsap.timeline({{ paused: true }}).to('#r', {{ x: 200, duration: 1, ease: 'power2.inOut' }}, 0);
window.__rm = {{ ready: true, seek(t) {{ tl.seek(t, false); }} }}; }})();</script></body></html>''')
    out = os.path.join(tmp, 'test.mp4')
    if '--keep' in sys.argv: print('  scène de test :', scene)
    r = subprocess.run(['node', os.path.join(ROOT, 'engine', 'render.mjs'), scene, out, '--start', '0', '--end', '1',
                        '--w', '320', '--h', '180'], capture_output=True, text=True)
    good = r.returncode == 0 and os.path.exists(out)
    line(good, 'rendu de test (1 s, 30 images)', (r.stderr or r.stdout).strip()[-400:])
    if good:
        V = rmcommon.probe(out)
        line(V['frames'] == 30 and (V['w'], V['h']) == (320, 180), f"vidéo de test : {V['frames']} images {V['w']}x{V['h']}", 'rendu incomplet')
    shutil.rmtree(tmp, ignore_errors=True)

print('Tout est prêt.' if ok else 'Il manque des éléments (voir ci-dessus).')
sys.exit(0 if ok else 1)
