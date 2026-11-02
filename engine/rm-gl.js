// reverse-motion WebGL layer.
// 1) Effect plates: a measured per-frame matte (see scripts/extract_plate.py) composited by a
//    fragment shader between two editable colours, with optional tint gradient and exact pixel
//    sampling (no filtering blur, no offset).
// 2) Parametric shaders for effects rebuilt from formulas (ripple displacement, pixel mosaic,
//    noise edge) — used when no source plate exists (rebrand variants, new videos).
(function () {
  const VS = `attribute vec2 p; varying vec2 uv; void main(){ uv = vec2(p.x * 0.5 + 0.5, 0.5 - p.y * 0.5); gl_Position = vec4(p, 0.0, 1.0); }`;
  const hex = h => { h = h.replace('#', ''); return [0, 2, 4].map(i => parseInt(h.slice(i, i + 2), 16) / 255); };

  function program(gl, fs) {
    const sh = (type, src) => { const s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s);
      if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s)); return s; };
    const pr = gl.createProgram(); gl.attachShader(pr, sh(gl.VERTEX_SHADER, VS)); gl.attachShader(pr, sh(gl.FRAGMENT_SHADER, fs));
    gl.linkProgram(pr); if (!gl.getProgramParameter(pr, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(pr));
    const buf = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
    const loc = gl.getAttribLocation(pr, 'p'); gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
    // several programs may share one canvas (one context): each draw must re-activate its own program and quad
    pr.use = () => { gl.useProgram(pr); gl.bindBuffer(gl.ARRAY_BUFFER, buf); gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0); };
    return pr;
  }
  function context(canvas) {
    if (canvas.__gl) return canvas.__gl;
    const gl = canvas.__gl = canvas.getContext('webgl', { preserveDrawingBuffer: true, premultipliedAlpha: false, antialias: false, alpha: true });
    if (!gl) throw new Error('WebGL indisponible');
    return gl;
  }
  function texture(gl, nearest) {
    const t = gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D, t);
    const f = nearest ? gl.NEAREST : gl.LINEAR;
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, f); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, f);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    return t;
  }

  // ---------- 1) effect plate ----------
  const PLATE_FS = `precision highp float; varying vec2 uv; uniform sampler2D m; uniform vec3 ca; uniform vec3 cb; uniform vec3 cc;
    uniform float three; uniform float opacity; uniform float gamma; uniform float rgb;
    void main(){ vec4 t = texture2D(m, uv); float a = pow(t.r, gamma);
      vec3 col = rgb > 0.5 ? t.rgb : (three > 0.5 ? ca + t.r * (cb - ca) + t.g * (cc - ca) : mix(ca, cb, a));
      gl_FragColor = vec4(col, opacity); }`;
  async function plate(canvas, data, opts = {}) {
    const gl = context(canvas), pr = program(gl, PLATE_FS), tex = texture(gl, true);
    gl.useProgram(pr);
    const imgs = {};
    // true-colour plates (extract_plate.py --rgb) are big: decoded on demand with a small cache, the renderer
    // waits for them (window.__rmWait) and seeks again. Matte plates are small: all decoded up front.
    const load = f => imgs[f] || (imgs[f] = new Promise((res, rej) => { const im = new Image();
      im.onload = () => { imgs[f] = im; res(im); }; im.onerror = rej; im.src = data.frames[f]; }));
    if (!data.rgb) await Promise.all(Object.keys(data.frames).map(load));
    const order = [];
    const U = n => gl.getUniformLocation(pr, n);
    const keys = Object.keys(data.frames).map(Number).sort((a, b) => a - b);
    const api = {
      first: keys[0], last: keys[keys.length - 1],
      has: f => data.frames[f] !== undefined,
      draw(f, o = {}) {
        if (data.frames[f] === undefined) { canvas.style.visibility = 'hidden'; return false; }
        let im = imgs[f];
        if (!(im instanceof Image)) {     // not decoded yet: ask the renderer to wait, keep the canvas as is
          (window.__rmPending = window.__rmPending || []).push(load(f)); return true; }
        if (data.rgb) { order.push(f); if (data.frames[f + 1] !== undefined && !imgs[f + 1]) load(f + 1);
          while (order.length > 8) { const old = order.shift(); if (old !== f) delete imgs[old]; } }
        canvas.style.visibility = 'visible';
        pr.use();
        gl.viewport(0, 0, canvas.width, canvas.height);
        gl.bindTexture(gl.TEXTURE_2D, tex); gl.pixelStorei(gl.UNPACK_ALIGNMENT, 1);
        const three = !!data.c;
        if (three || data.rgb) gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGB, gl.RGB, gl.UNSIGNED_BYTE, im);
        else gl.texImage2D(gl.TEXTURE_2D, 0, gl.LUMINANCE, gl.LUMINANCE, gl.UNSIGNED_BYTE, im);
        const remap = c => RM.brandColor(c);
        gl.uniform3fv(U('ca'), hex(remap(o.a || opts.a || data.a))); gl.uniform3fv(U('cb'), hex(remap(o.b || opts.b || data.b)));
        gl.uniform3fv(U('cc'), hex(remap(data.c || '#000000'))); gl.uniform1f(U('three'), three ? 1 : 0); gl.uniform1f(U('rgb'), data.rgb ? 1 : 0);
        gl.uniform1f(U('opacity'), o.opacity ?? 1); gl.uniform1f(U('gamma'), o.gamma ?? opts.gamma ?? 1);
        gl.uniform1i(U('m'), 0); gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4); return true;
      },
    };
    return api;
  }

  // ---------- 2) parametric shaders ----------
  const RIPPLE_FS = `precision highp float; varying vec2 uv; uniform sampler2D src; uniform vec2 res; uniform vec2 c; uniform float t;
    uniform float speed; uniform float width; uniform float amp; uniform float glow; uniform float rings; uniform float gap; uniform vec3 tint;
    void main(){ vec2 px = uv * res; vec2 d = px - c; float r = length(d); vec2 n = d / max(r, 1e-3);
      float h = 0.0, dh = 0.0;
      for (int k = 0; k < 4; k++) { if (float(k) >= rings) break; float R = (t - float(k) * gap) * speed; if (R <= 0.0) continue;
        float life = clamp(1.0 - R / (speed * 1.4), 0.0, 1.0); float x = (r - R) / width; float g = exp(-x * x) * life;
        h += g; dh += -2.0 * x / width * g; }
      float side = pow(abs(n.x), 0.6);
      vec4 base = texture2D(src, (px - n * dh * amp * side) / res);
      gl_FragColor = vec4(mix(base.rgb, tint, clamp(h * glow * side, 0.0, 1.0)), 1.0); }`;
  const MOSAIC_FS = `precision highp float; varying vec2 uv; uniform sampler2D src; uniform vec2 res; uniform float block; uniform vec2 offset;
    void main(){ vec2 px = uv * res; vec2 cell = (floor((px - offset) / block) + 0.5) * block + offset; gl_FragColor = texture2D(src, cell / res); }`;
  function effect(canvas, fs) {
    const gl = context(canvas), pr = program(gl, fs), tex = texture(gl, false);
    const U = n => gl.getUniformLocation(pr, n);
    return {
      draw(source, uniforms) {
        pr.use(); gl.viewport(0, 0, canvas.width, canvas.height);
        gl.bindTexture(gl.TEXTURE_2D, tex); gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, source);
        gl.uniform2f(U('res'), canvas.width, canvas.height); gl.uniform1i(U('src'), 0);
        for (const [k, v] of Object.entries(uniforms)) {
          const l = U(k); if (!l) continue;
          if (Array.isArray(v)) (v.length === 2 ? gl.uniform2fv : gl.uniform3fv).call(gl, l, v); else gl.uniform1f(l, v);
        }
        gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
      },
    };
  }
  // ---------- 3) décalque mode for a whole scene ----------
  // opts: { plateCanvas, prefix, ranges: {name: [f0, f1]}, bgIds: [...], shapeIds: [...], skinIds: [...], fgIds: [...], P }
  //  - ?holes=1 (render.mjs --holes) : page background, bgIds and shapeIds hidden, skins stripped -> only rebuilt foreground (holes source)
  //  - P.show (array, from #hash) : only these fgIds stay visible (choose which elements become holes)
  //  - P.usePlates === false : pure code mode (rebrand), plates never drawn
  //  - while a plate covers the frame : shapeIds hidden, skinIds lose background/shadow (their text stays)
  //  - window.HIDE[frame] (ghost_guard.py) : these fgIds are hidden in that frame, the plate shows the original
  async function decalque(o) {
    const $ = id => document.getElementById(id), P = o.P || {};
    const T = location.search.includes('holes');
    const st = document.createElement('style');
    st.textContent = '.rm-noskin{background:transparent!important;box-shadow:none!important;border-color:transparent!important}.rm-ghost{visibility:hidden!important}';
    document.head.appendChild(st);
    if (T) {
      document.documentElement.style.background = 'transparent'; document.body.style.background = 'transparent';
      for (const el of document.querySelectorAll('#stage, #stage > svg > rect:first-child')) el.style.background = 'transparent';
      for (const id of [...(o.bgIds || []), ...(o.shapeIds || [])]) { const e = $(id); if (e) e.style.display = 'none'; }
      for (const id of o.skinIds || []) { const e = $(id); if (e) e.classList.add('rm-noskin'); }
    }
    if (P.show) for (const id of o.fgIds || []) if (!P.show.includes(id)) { const e = $(id); if (e) e.style.opacity = '0'; }
    if (window.BRAND) { RM.applyBrand(); if (BRAND.mode === 'code') P.usePlates = false; }
    window.__rmFg = o.fgIds || []; // read by ghost_guard.py
    const PL = {};
    if (!T && P.usePlates !== false && window.PLATES)
      for (const k of Object.keys(o.ranges)) if (PLATES[o.prefix + k]) PL[k] = await plate($(o.plateCanvas), PLATES[o.prefix + k]);
    return {
      transparent: T,
      seek(t) {
        const f = Math.round(t * RM.FPS); let on = null;
        for (const k in PL) if (f >= o.ranges[k][0] && f <= o.ranges[k][1] && PL[k].has(f)) on = k;
        if (on) PL[on].draw(f); else if ($(o.plateCanvas)) $(o.plateCanvas).style.visibility = 'hidden';
        if (!T) {
          for (const id of o.shapeIds || []) { const e = $(id); if (e) e.style.visibility = on ? 'hidden' : ''; }
          for (const id of o.skinIds || []) { const e = $(id); if (e) e.classList.toggle('rm-noskin', !!on); }
        }
        // ghost guard (scripts/ghost_guard.py -> window.HIDE = {frame: [ids]}): in these frames the rebuilt element
        // does not match the original, so it is hidden and the plate shows the original pixels instead (no double).
        // Applied in hole renders too, so that the plate keeps those pixels instead of inpainting them.
        const inRange = Object.values(o.ranges).some(([a, b]) => f >= a && f <= b);
        const hide = (P.usePlates !== false && (T ? inRange : !!on) && window.HIDE && window.HIDE[f]) || [];
        for (const id of o.fgIds || []) { const e = $(id); if (e) e.classList.toggle('rm-ghost', hide.includes(id)); }
        if (window.RM && RM.applyReg) RM.applyReg(t);
        return on;
      },
    };
  }
  // renderers call this after seek(t): resolves when every plate image asked for by that seek is decoded
  window.__rmWait = async () => { const p = window.__rmPending || []; window.__rmPending = []; await Promise.all(p); return p.length; };
  window.RMGL = { decalque, plate, effect, RIPPLE_FS, MOSAIC_FS, hex };
})();
