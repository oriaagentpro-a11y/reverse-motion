// Render an HTML/GSAP scene frame by frame, then encode it with ffmpeg.
// Usage: node render.mjs <scene.html> <out.mp4> --fps 30 --start 0 --end 5 --w 736 --h 414 [--frames-dir dir] [--audio src.mp4] [--brand brand.js]
// The page must expose window.__rm = { seek(t) } that puts every animation at time t (seconds).
import { chromium } from 'playwright';
import { execFileSync } from 'node:child_process';
import { mkdirSync, rmSync, existsSync, writeFileSync, readdirSync } from 'node:fs';
import os from 'node:os';
import { PNG } from 'pngjs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const args = process.argv.slice(2);
const opt = (k, d) => { const i = args.indexOf('--' + k); return i >= 0 ? args[i + 1] : d; };
const [html, out] = args;
const fps = Number(opt('fps', 30)), start = Number(opt('start', 0)), end = Number(opt('end', 5));
const W = Number(opt('w', 736)), H = Number(opt('h', 414));
const framesDir = opt('frames-dir', out.replace(/\.mp4$/, '_frames'));
const audio = opt('audio', null);
const holes = args.includes('--holes'); // foreground-only render used to punch plate holes (implies transparent)
const transparent = args.includes('--transparent') || holes;
const hash = opt('hash', ''); // JSON overrides passed to the scene (#...), e.g. which elements to show // PNG frames with alpha, for layering (no mp4 when out ends with /)
const exe = findChrome();

// Browser: $CHROME_PATH, else Playwright's own Chromium, else any installed Chromium / Chrome / Edge.
function findChrome() {
  if (process.env.CHROME_PATH) return process.env.CHROME_PATH;
  try { const p = chromium.executablePath(); if (p && existsSync(p)) return p; } catch { /* not installed */ }
  const home = os.homedir(), roots = [process.env.PLAYWRIGHT_BROWSERS_PATH, path.join(home, '.cache/ms-playwright'),
    path.join(home, 'Library/Caches/ms-playwright'), process.env.LOCALAPPDATA && path.join(process.env.LOCALAPPDATA, 'ms-playwright'), '/opt/pw-browsers'];
  const inner = ['chrome-linux64/chrome', 'chrome-linux/chrome', 'chrome-win/chrome.exe', 'chrome-win64/chrome.exe',
    'chrome-mac/Chromium.app/Contents/MacOS/Chromium', 'chrome-mac-arm64/Chromium.app/Contents/MacOS/Chromium'];
  for (const r of roots) { if (!r || !existsSync(r)) continue;
    for (const d of readdirSync(r).filter(n => n.startsWith('chromium-')).sort().reverse())
      for (const i of inner) { const p = path.join(r, d, i); if (existsSync(p)) return p; } }
  const sys = ['/usr/bin/chromium', '/usr/bin/chromium-browser', '/usr/bin/google-chrome', '/usr/bin/google-chrome-stable', '/snap/bin/chromium',
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/Applications/Chromium.app/Contents/MacOS/Chromium',
    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe', 'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe'];
  return sys.find(existsSync); // undefined -> Playwright reports a clear error
}

rmSync(framesDir, { recursive: true, force: true });
mkdirSync(framesDir, { recursive: true });
const browser = await chromium.launch({ executablePath: exe, args: ['--force-color-profile=srgb', '--disable-lcd-text', '--font-render-hinting=none'] });
const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
page.on('pageerror', e => console.error('page error:', e.message));
// --brand brand.js : the brand file is injected before any scene script (window.BRAND), no scene edit needed
const brand = opt('brand', null);
if (brand) await page.addInitScript({ path: path.resolve(brand) });
await page.goto(pathToFileURL(path.resolve(html)).href + `?fps=${fps}` + (holes ? '&holes=1' : (transparent ? '&transparent=1' : '')) + (hash ? '#' + encodeURIComponent(hash) : ''));
await page.waitForFunction(() => window.__rm && window.__rm.ready === true, null, { timeout: 30000 });
await page.evaluate(() => document.fonts.ready);
const f0 = Math.round(start * fps), f1 = Math.round(end * fps);
// Motion blur: a scene may expose window.__rm.blurAt(t) -> [samples, shutter] (shutter in frames, 0.5 = 180 deg).
// The frame is then the average of `samples` renders spread over the shutter, like a camera / After Effects.
let blurred = 0;
for (let f = f0; f < f1; f++) {
  const out = path.join(framesDir, `f_${String(f - f0).padStart(5, '0')}.png`);
  const mb = await page.evaluate(t => (window.__rm.blurAt ? window.__rm.blurAt(t) : null), f / fps);
  if (!mb || mb[0] <= 1) {
    await page.evaluate(async t => { window.__rm.seek(t); if (window.__rmWait && await window.__rmWait()) window.__rm.seek(t); }, f / fps);
    await page.screenshot({ path: out, omitBackground: transparent });
    continue;
  }
  const [n, shutter] = mb; let acc = null, w = 0, h = 0;
  for (let i = 0; i < n; i++) {
    const t = (f + ((i + 0.5) / n - 0.5) * shutter) / fps;
    await page.evaluate(async tt => { window.__rm.seek(tt); if (window.__rmWait && await window.__rmWait()) window.__rm.seek(tt); }, t);
    const img = PNG.sync.read(await page.screenshot({ omitBackground: transparent }));
    if (!acc) { w = img.width; h = img.height; acc = new Float32Array(img.data.length); }
    if (transparent) { for (let k = 0; k < img.data.length; k += 4) { const a = img.data[k + 3] / 255;
        acc[k] += img.data[k] * a; acc[k + 1] += img.data[k + 1] * a; acc[k + 2] += img.data[k + 2] * a; acc[k + 3] += img.data[k + 3]; } }
    else for (let k = 0; k < img.data.length; k++) acc[k] += img.data[k];
  }
  const png = new PNG({ width: w, height: h });
  for (let k = 0; k < acc.length; k += 4) {
    if (transparent) { const a = acc[k + 3] / n; const inv = a > 0 ? 255 / (a * n) : 0;
      png.data[k] = Math.round(acc[k] * inv); png.data[k + 1] = Math.round(acc[k + 1] * inv); png.data[k + 2] = Math.round(acc[k + 2] * inv); png.data[k + 3] = Math.round(a); }
    else { png.data[k] = Math.round(acc[k] / n); png.data[k + 1] = Math.round(acc[k + 1] / n); png.data[k + 2] = Math.round(acc[k + 2] / n); png.data[k + 3] = 255; }
  }
  writeFileSync(out, PNG.sync.write(png)); blurred++;
}
if (blurred) console.log(`motion blur on ${blurred} frames`);
await browser.close();
if (transparent) { console.log(`rendered ${f1 - f0} transparent frames -> ${framesDir}`); process.exit(0); }
const enc = ['-y', '-v', 'error', '-framerate', String(fps), '-i', path.join(framesDir, 'f_%05d.png')];
if (audio) enc.push('-ss', String(start), '-t', String(end - start), '-i', audio, '-map', '0:v', '-map', '1:a', '-c:a', 'aac', '-shortest');
enc.push('-c:v', 'libx264', '-preset', 'veryfast', '-crf', '12', '-pix_fmt', 'yuv420p', out);
execFileSync('ffmpeg', enc, { stdio: 'inherit' });
// the PNG frames are only a step towards the mp4: removed unless asked for (--frames-dir or --keep-frames)
if (!args.includes('--frames-dir') && !args.includes('--keep-frames')) rmSync(framesDir, { recursive: true, force: true });
console.log(`rendered ${f1 - f0} frames -> ${out}`);
