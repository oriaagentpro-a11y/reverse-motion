// reverse-motion runtime: shared helpers for every reconstructed scene.
// Load after gsap. Fonts: one variable family "RM" (weight set per text element).
(function () {
  const deepMerge = (a, b) => {
    for (const k in b) a[k] = (b[k] && typeof b[k] === 'object' && !Array.isArray(b[k])) ? deepMerge(a[k] || {}, b[k]) : b[k];
    return a;
  };
  const ctx = document.createElement('canvas').getContext('2d');
  const measure = (text, size, weight, family = 'RM') => {
    ctx.font = `${weight} ${size}px ${family}`;
    return ctx.measureText(text);
  };
  const inkBox = m => ({
    w: m.actualBoundingBoxLeft + m.actualBoundingBoxRight,
    h: m.actualBoundingBoxAscent + m.actualBoundingBoxDescent,
  });

  // Place an SVG <text> so its ink box starts at (left, top).
  function placeInk(el, left, top) {
    const m = measure(el.textContent, el.getAttribute('font-size'), el.getAttribute('font-weight'));
    el.setAttribute('x', left + m.actualBoundingBoxLeft);
    el.setAttribute('y', top + m.actualBoundingBoxAscent);
  }
  // Size an SVG <text> so its ink is exactly `width` wide (or `height` tall), at weight `wt`.
  function sizeInk(el, { w, h, wt }) {
    if (wt != null) el.setAttribute('font-weight', wt);
    const box = inkBox(measure(el.textContent, 100, el.getAttribute('font-weight')));
    const size = w != null ? 100 * w / box.w : 100 * h / box.h;
    el.setAttribute('font-size', size.toFixed(3));
    return size;
  }
  // Size + place by ink box: spec = { left, top, w | h, wt } or { cx, cy, w | h, wt }.
  // Rebrand: if window.BRAND.texts[id] exists, the size is taken from the ORIGINAL word, then the new
  // text replaces it with the same size and the same anchor (left edge, or centre when spec.cx is set).
  // A new text wider than the original is scaled down to the original's width (it would overlap the next
  // word otherwise), vertically centred on the original ink box. BRAND.fit = false keeps the full size.
  function fitInk(el, spec) {
    const nt = window.BRAND && BRAND.texts && el.id && BRAND.texts[el.id];
    if (nt != null) { if (el.dataset.origText == null) el.dataset.origText = el.textContent; el.textContent = el.dataset.origText; }
    sizeInk(el, spec);
    const fs = () => el.getAttribute('font-size'), fw = () => el.getAttribute('font-weight');
    const b0 = inkBox(measure(el.textContent, fs(), fw()));
    if (nt == null) { if (spec.cx != null) placeInk(el, spec.cx - b0.w / 2, spec.cy - b0.h / 2); else placeInk(el, spec.left, spec.top); return; }
    el.textContent = nt; el.dataset.rebranded = '1';
    let b = inkBox(measure(nt, fs(), fw()));
    let dy = 0;
    if (BRAND.fit !== false && b.w > b0.w * 1.02) {
      el.setAttribute('font-size', (fs() * b0.w / b.w).toFixed(3)); const nb = inkBox(measure(nt, fs(), fw()));
      dy = (b0.h - nb.h) / 2; b = nb;
    }
    if (spec.cx != null) placeInk(el, spec.cx - b.w / 2, spec.cy - b0.h / 2 + dy);
    else placeInk(el, spec.left, spec.top + dy);
  }
  // Rebrand colours. brandColor(c): exact key of BRAND.colors -> its value; a colour NEAR a key (anti-aliasing,
  // measured shades such as rgb(87,0,185) next to #5000B0) is moved by the same difference, so shades follow.
  // Canvas code must draw with RM.brandColor('#5000B0') instead of a literal, or the rebrand misses it.
  const hexOf = v => '#' + v.map(x => Math.round(Math.min(255, Math.max(0, x))).toString(16).padStart(2, '0')).join('');
  const rgbOf = c => { if (!c) return null; c = String(c).trim().toLowerCase();
    let m = c.match(/^rgba?\((\d+(?:\.\d+)?),\s*(\d+(?:\.\d+)?),\s*(\d+(?:\.\d+)?)/); if (m) return [+m[1], +m[2], +m[3]];
    if (/^#[0-9a-f]{3}$/.test(c)) c = '#' + c.slice(1).split('').map(x => x + x).join('');
    m = c.match(/^#([0-9a-f]{6})$/); return m ? [0, 2, 4].map(i => parseInt(m[1].slice(i, i + 2), 16)) : null; };
  let brandKeys = null;
  function brandColor(c, near = 40) {
    const B = window.BRAND; if (!B || !B.colors) return c; const v = rgbOf(c); if (!v) return c;
    if (!brandKeys) brandKeys = Object.entries(B.colors).map(([k, x]) => [rgbOf(k), rgbOf(x)]).filter(([k, x]) => k && x);
    let best = null, bd = 1e9; for (const [k, x] of brandKeys) { const d = Math.hypot(v[0] - k[0], v[1] - k[1], v[2] - k[2]); if (d < bd) { bd = d; best = [k, x]; } }
    if (!best || bd > near) return c;
    const out = hexOf(v.map((x, i) => x + best[1][i] - best[0][i]));
    // keep the alpha whatever its syntax (0.5, 1e-7, 50%): with [\d.]+ a tiny alpha written 1e-7 was lost -> opaque glow
    const a = String(c).match(/^rgba\([^,]+,[^,]+,[^,]+,\s*([^)]+)\)/); return a ? `rgba(${rgbOf(out).join(',')},${a[1]})` : out;
  }
  function applyBrand(root = document) {
    const B = window.BRAND; if (!B || !B.colors) return; brandKeys = null;
    for (const el of root.querySelectorAll('*')) {
      for (const a of ['fill', 'stroke', 'stop-color']) { const v = el.getAttribute(a); if (v && rgbOf(v)) { const n = brandColor(v); if (n !== v) el.setAttribute(a, n); } }
      const cs = el.style; for (const prop of ['color', 'backgroundColor', 'fill', 'stroke']) { const v = cs[prop]; if (v && rgbOf(v)) { const n = brandColor(v); if (n !== v) cs[prop] = n; } }
    }
    for (const sh of document.styleSheets) { try { for (const r of sh.cssRules) if (r.style) for (const prop of ['color', 'background', 'background-color', 'fill', ...Array.from(r.style).filter(p => p.startsWith('--'))]) {
      const v = r.style.getPropertyValue(prop).trim(); if (v && rgbOf(v)) { const n = brandColor(v); if (n !== v) r.style.setProperty(prop, n); } } } catch (e) {} }
  }
  const overrides = () => JSON.parse(decodeURIComponent(location.hash.slice(1) || '{}'));
  async function fontsReady(weights = [300, 400, 500, 600, 700, 800]) {
    await Promise.all(weights.map(w => document.fonts.load(`${w} 40px RM`)));
    await document.fonts.ready;
  }
  // A background grid of crisp 1 px lines at measured x / y positions, with a softer second pixel.
  // Positions and colours come from the project (measured on its video), never from the engine.
  function drawGrid(ctx, gx, gy, alpha = 1, line = 'rgb(87,0,185)', soft = 'rgb(105,2,204)') {
    line = brandColor(line); soft = brandColor(soft);
    ctx.save(); ctx.globalAlpha = alpha;
    ctx.fillStyle = line;
    for (const x of gx) ctx.fillRect(x + 1, 0, 1, ctx.canvas.height);
    for (const y of gy) ctx.fillRect(0, y + 1, ctx.canvas.width, 1);
    ctx.fillStyle = soft;
    for (const x of gx) ctx.fillRect(x, 0, 1, ctx.canvas.height);
    for (const y of gy) ctx.fillRect(0, y, ctx.canvas.width, 1);
    ctx.restore();
  }
  // Frame rate of the source: render.mjs / the Python tools pass ?fps=, a scene may also set window.RM_FPS.
  const FPS = Number(new URLSearchParams(location.search).get('fps')) || window.RM_FPS || 30;
  // Homography: CSS matrix3d that maps a w x h element (transform-origin 0 0) onto a measured quad
  // [[x,y] top-left, top-right, bottom-right, bottom-left]. Used to replay tracked cards image by image.
  function quadMatrix3d(w, h, q) {
    const src = [[0, 0], [w, 0], [w, h], [0, h]], A = [], b = [];
    for (let i = 0; i < 4; i++) { const [x, y] = src[i], [u, v] = q[i];
      A.push([x, y, 1, 0, 0, 0, -u * x, -u * y]); b.push(u); A.push([0, 0, 0, x, y, 1, -v * x, -v * y]); b.push(v); }
    for (let c = 0; c < 8; c++) { let p = c; for (let r = c + 1; r < 8; r++) if (Math.abs(A[r][c]) > Math.abs(A[p][c])) p = r;
      [A[c], A[p]] = [A[p], A[c]]; [b[c], b[p]] = [b[p], b[c]];
      for (let r = 0; r < 8; r++) if (r !== c) { const k = A[r][c] / A[c][c]; for (let j = c; j < 8; j++) A[r][j] -= k * A[c][j]; b[r] -= k * b[c]; } }
    const H = b.map((v, i) => v / A[i][i]);
    return `matrix3d(${H[0]},${H[3]},0,${H[6]},${H[1]},${H[4]},0,${H[7]},0,0,1,0,${H[2]},${H[5]},0,1)`;
  }
  // CSS matrix3d of a 3x3 homography given row-major [h00..h22] (maps reference-frame coordinates to the
  // frame's coordinates; element with transform-origin 0 0 laid out in reference coordinates).
  function homographyMatrix3d(h) {
    return `matrix3d(${h[0]},${h[3]},0,${h[6]},${h[1]},${h[4]},0,${h[7]},0,0,1,0,${h[2]},${h[5]},0,${h[8]})`;
  }
  // Read a per-frame track at a fractional frame (linear between measured frames; null outside).
  function trackAt(rows, f, key) {
    const f0 = Math.floor(f), f1 = Math.ceil(f), a = rows[f0], b = rows[f1];
    if (!a && !b) return null; if (!a || !b || f0 === f1) return (a || b)[key];
    const p = f - f0, va = a[key], vb = b[key];
    const mix = (x, y) => Array.isArray(x) ? x.map((v, i) => mix(v, y[i])) : x + (y - x) * p;
    return mix(va, vb);
  }
  // Replay per-frame registration corrections (scripts/register.py) with CSS individual transforms,
  // which compose with GSAP's own transform. Fractional frames interpolate between measured frames.
  const regTouched = new Set();
  function applyReg(t) {
    const R = window.REG; if (!R) return; const ff = t * FPS, f0 = Math.floor(ff), f1 = Math.ceil(ff), p = ff - f0;
    const a = R[f0] || {}, b = R[f1] || {}, ids = new Set([...Object.keys(a), ...Object.keys(b), ...regTouched]);
    for (const id of ids) {
      const el = document.getElementById(id); if (!el || el.dataset.rebranded) continue; regTouched.add(id);
      const A = a[id], B = b[id];
      if (!A && !B) { el.style.translate = el.style.scale = el.style.rotate = ''; if (el.dataset.regOpacity) { el.style.opacity = ''; delete el.dataset.regOpacity; } continue; }
      const g = (o, k, d) => (o && o[k] != null ? o[k] : d);
      const v = k => { const d = (k === 's' || k === 'o') ? 1 : 0; const x = g(A, k, A ? d : g(B, k, d)), y = g(B, k, B ? d : x); return x + (y - x) * p; };
      el.style.transformBox = 'fill-box'; el.style.transformOrigin = 'center';
      el.style.translate = `${v('dx')}px ${v('dy')}px`; el.style.scale = `${v('s')}`; el.style.rotate = `${v('r')}deg`;
      const o = v('o'); if (o !== 1 || el.dataset.regOpacity) { el.style.opacity = o; el.dataset.regOpacity = '1'; }
    }
  }
  window.RM = { applyBrand, brandColor, applyReg, quadMatrix3d, homographyMatrix3d, trackAt, drawGrid, FPS, deepMerge, measure, inkBox, placeInk, sizeInk, fitInk, overrides, fontsReady,
    lerp: (a, b, p) => a + (b - a) * p, clamp: (v, a = 0, b = 1) => Math.min(b, Math.max(a, v)) };
})();
