"""Shared helpers: find a Chromium to drive, read a video's frame rate / size, build scene URLs.

Every script imports this module, so nothing depends on one machine's paths:
- the browser comes from $CHROME_PATH, else Playwright's own Chromium, else a system Chrome / Chromium / Edge;
- the frame rate and the frame size come from the source video (ffprobe), never from constants.
"""
import os, sys, json, glob, shutil, subprocess, urllib.parse, pathlib

BROWSER_ARGS = ['--force-color-profile=srgb', '--disable-lcd-text', '--font-render-hinting=none']

_SYSTEM_BROWSERS = [
    # Linux
    '/usr/bin/chromium', '/usr/bin/chromium-browser', '/usr/bin/google-chrome', '/usr/bin/google-chrome-stable',
    '/snap/bin/chromium', '/usr/bin/microsoft-edge',
    # macOS
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Chromium.app/Contents/MacOS/Chromium',
    '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
    # Windows
    r'C:\Program Files\Google\Chrome\Application\chrome.exe',
    r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
    r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
]


def chrome_path():
    """Executable to pass to Playwright, or None to let Playwright use the Chromium it installed."""
    env = os.environ.get('CHROME_PATH')
    if env:
        return env
    # Playwright's own browsers (pip/npm "playwright install chromium"), wherever they were installed
    roots = [os.environ.get('PLAYWRIGHT_BROWSERS_PATH', ''), os.path.expanduser('~/.cache/ms-playwright'),
             os.path.expanduser('~/Library/Caches/ms-playwright'),
             os.path.join(os.environ.get('LOCALAPPDATA', ''), 'ms-playwright'), '/opt/pw-browsers']
    pats = ['chromium-*/chrome-linux*/chrome', 'chromium-*/chrome-mac*/Chromium.app/Contents/MacOS/Chromium',
            'chromium-*/chrome-mac*/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing',
            'chromium-*/chrome-win*/chrome.exe']
    for r in roots:
        if r and os.path.isdir(r):
            hits = sorted(h for p in pats for h in glob.glob(os.path.join(r, p)))
            if hits:
                return hits[-1]
    for p in _SYSTEM_BROWSERS:
        if os.path.exists(p):
            return p
    return shutil.which('chromium') or shutil.which('google-chrome') or None


def launch(pw):
    """Launch Chromium with the colour settings the comparison relies on (sRGB, no LCD subpixel text)."""
    exe = chrome_path()
    kw = {'args': BROWSER_ARGS}
    if exe:
        kw['executable_path'] = exe
    try:
        return pw.chromium.launch(**kw)
    except Exception as e:  # noqa: BLE001 - give a usable message instead of a stack trace
        sys.exit(f'Chromium introuvable ou impossible à lancer ({e}).\n'
                 f'Lancez "python3 -m playwright install chromium" ou définissez CHROME_PATH.')


def probe(video):
    """{'fps': float, 'w': int, 'h': int, 'duration': float, 'frames': int} of a video file."""
    out = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                          'stream=width,height,r_frame_rate,nb_frames:format=duration', '-of', 'json', video],
                         capture_output=True, text=True, check=True).stdout
    j = json.loads(out); s = j['streams'][0]
    num, den = s['r_frame_rate'].split('/')
    fps = float(num) / float(den)
    dur = float(j.get('format', {}).get('duration', 0) or 0)
    n = int(s['nb_frames']) if str(s.get('nb_frames', '')).isdigit() else round(dur * fps)
    return {'fps': fps, 'w': int(s['width']), 'h': int(s['height']), 'duration': dur, 'frames': n}


def scene_url(scene, fps=30, query=None, hash_obj=None):
    """file:// URL of a scene, with ?fps= (read by RM.FPS) and optional #{json overrides}."""
    q = {'fps': f'{fps:g}', **(query or {})}
    url = pathlib.Path(os.path.abspath(scene)).as_uri() + '?' + urllib.parse.urlencode(q)
    if hash_obj:
        url += '#' + urllib.parse.quote(json.dumps(hash_obj))
    return url


def arg(argv, name, default=None, cast=str):
    """Value of --name in argv (or default)."""
    k = '--' + name
    return cast(argv[argv.index(k) + 1]) if k in argv else default
