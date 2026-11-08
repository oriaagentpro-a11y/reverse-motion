// reverse-motion · 3D objects (icons, badges, coins, phones, cards...) placed on the pose measured on the video.
// Load after rm.js and rm-gl.js. Two modes, same pose (scripts/fit_object_pose.py -> window.POSES[name]):
//   'frames' : the Cycles renders of scripts/blender_object.py (RGBA PNG per frame) drawn on the object's canvas.
//              Highest fidelity (path tracing, motion blur, materials calibrated on the video).
//   'live'   : the same model (GLB exported by blender_object.py --glb, embedded by --glb as <name>.glb.js because
//              file:// pages cannot fetch) rendered live with Three.js (vendor/three-rm.js, built by `npm install`).
//              Fully editable in code: colours, lights, pose, timing.
// The canvas is a foreground element like any other: give its id to RMGL.decalque({ fgIds }) so that the hole
// renders cut it out of the plate and the ghost guard can hide it on frames where it does not match.
//
//   const ob = await RM3D.object({ canvas: 'icon3d', pose: POSES.icon, mode: 'frames',
//                                   dir: '../obj3d/frames/', spec: OBJ3D.icon, glb: 'icon' });
//   ... in seek(t): ob.seek(f)
(function () {
  const keyed = (keys, f, d = 1) => {
    if (!keys) return d;
    const ks = Object.entries(keys).map(([k, v]) => [+k, v]).sort((a, b) => a[0] - b[0]);
    if (f <= ks[0][0]) return ks[0][1];
    for (let i = 0; i + 1 < ks.length; i++) {
      const [f0, v0] = ks[i], [f1, v1] = ks[i + 1];
      if (f >= f0 && f <= f1) return v0 + (v1 - v0) * (f - f0) / Math.max(1, f1 - f0);
    }
    return ks[ks.length - 1][1];
  };
  // OpenCV pose (solvePnP: x right, y down, z forward; R = Rz.Ry.Rx from rot_deg) -> Three.js camera axes
  // (y up, looking down -z): M = C R C, t' = (x, -y, -z) with C = diag(1, -1, -1). Same as blender_object.place().
  function poseMatrix(THREE, p) {
    const [ax, ay, az] = p.rot_deg.map(v => v * Math.PI / 180);
    const cx = Math.cos(ax), sx = Math.sin(ax), cy = Math.cos(ay), sy = Math.sin(ay), cz = Math.cos(az), sz = Math.sin(az);
    const R = [[cz * cy, cz * sy * sx - sz * cx, cz * sy * cx + sz * sx],
               [sz * cy, sz * sy * sx + cz * cx, sz * sy * cx - cz * sx],
               [-sy, cy * sx, cy * cx]];
    const c = [1, -1, -1], t = [p.pos[0], -p.pos[1], -p.pos[2]];
    const m = new THREE.Matrix4();
    m.set(c[0] * c[0] * R[0][0], c[0] * c[1] * R[0][1], c[0] * c[2] * R[0][2], t[0],
          c[1] * c[0] * R[1][0], c[1] * c[1] * R[1][1], c[1] * c[2] * R[1][2], t[1],
          c[2] * c[0] * R[2][0], c[2] * c[1] * R[2][1], c[2] * c[2] * R[2][2], t[2],
          0, 0, 0, 1);
    return m;
  }
  const b64 = s => { const b = atob(s), u = new Uint8Array(b.length); for (let i = 0; i < b.length; i++) u[i] = b.charCodeAt(i); return u.buffer; };

  async function object(o) {
    const cv = typeof o.canvas === 'string' ? document.getElementById(o.canvas) : o.canvas;
    const pose = o.pose, spec = o.spec || {}, W = pose.w, H = pose.h;
    cv.width = W; cv.height = H;
    const frames = Object.keys(pose.frames).map(Number).sort((a, b) => a - b);
    const [f0, f1] = o.range || [frames[0], frames[frames.length - 1]];
    const has = f => f >= f0 && f <= f1 && pose.frames[f];
    if (o.mode !== 'live') {
      // ---- Blender frames: one RGBA PNG per frame, decoded lazily (render.mjs waits through window.__rmWait)
      const ctx = cv.getContext('2d'), cache = {};
      const img = f => {
        if (!cache[f]) {
          const im = new Image(); im.src = `${o.dir}f_${String(f).padStart(5, '0')}.png`;
          cache[f] = im; (window.__rmPending = window.__rmPending || []).push(im.decode().catch(() => 0));
        }
        return cache[f];
      };
      return {
        mode: 'frames',
        seek(f) {
          ctx.clearRect(0, 0, W, H);
          if (!has(f)) { cv.style.visibility = 'hidden'; return false; }
          cv.style.visibility = ''; const im = img(f);
          const draw = () => { ctx.clearRect(0, 0, W, H); ctx.drawImage(im, 0, 0, W, H); };
          if (im.complete && im.naturalWidth) draw(); else im.decode().then(draw).catch(() => 0);
          return true;
        },
      };
    }
    // ---- live Three.js
    const THREE = window.THREE;
    if (!THREE || !THREE.GLTFLoader) throw new Error('rm-3d : vendor/three-rm.js manquant (cd engine && npm install)');
    const renderer = new THREE.WebGLRenderer({ canvas: cv, alpha: true, antialias: true, preserveDrawingBuffer: true });
    renderer.setPixelRatio(1); renderer.setSize(W, H, false); renderer.setClearColor(0x000000, 0);
    renderer.outputEncoding = THREE.sRGBEncoding; renderer.physicallyCorrectLights = true;
    renderer.toneMapping = THREE.NoToneMapping;
    const scene = new THREE.Scene();
    const cam = new THREE.PerspectiveCamera(pose.fov, W / H, 0.05, 100);   // at the origin, looking down -z
    const gltf = await new Promise((res, rej) => new THREE.GLTFLoader().parse(b64(window.RM_GLB[o.glb]), '', res, rej));
    const root = new THREE.Group(); root.matrixAutoUpdate = false; scene.add(root);
    const model = gltf.scene; root.add(model);
    model.traverse(n => { if (n.isLight) n.visible = false; if (n.isMesh) n.material.side = THREE.DoubleSide; });   // Blender renders both sides: same here (text meshes may face away)    // lights come from the spec, below
    // lights: the spec's (same positions as in Blender, fixed to the object), area lights as directional + world
    const exposure = Math.pow(2, spec.exposure || 0), tot = (spec.lights || []).reduce((s, l) => s + (l.energy || 300), 0) || 1;
    for (const L of spec.lights || []) {
      const d = new THREE.DirectionalLight(new THREE.Color(L.color || '#FFFFFF'), (o.lightGain || (spec.live && spec.live.gain) || 3.2) * exposure * (L.energy || 300) / tot);
      d.position.set(...(L.pos || [-2, 3, 4])); root.add(d); root.add(d.target);
    }
    const wc = (spec.world && spec.world.color) || '#FFFFFF';
    scene.add(new THREE.HemisphereLight(new THREE.Color('#FFFFFF'), new THREE.Color(wc), (o.ambient || (spec.live && spec.live.ambient) || 1.1) * exposure * ((spec.world && spec.world.strength) || 0.5)));
    const parts = {}; model.traverse(n => { parts[n.name] = n; });
    model.updateMatrixWorld(true);   // local matrices from the glTF TRS (else identity until the first render)
    const base = {}; for (const k in parts) base[k] = parts[k].matrix.clone();
    return {
      mode: 'live', scene, model, renderer,
      seek(f) {
        if (!has(f)) { cv.style.visibility = 'hidden'; return false; }
        cv.style.visibility = '';
        root.matrix.copy(poseMatrix(THREE, pose.frames[f])); root.matrixWorldNeedsUpdate = true;
        (spec.badges || []).forEach((bd, i) => {          // badge pop measured on the video (scale_keys)
          const s = keyed(bd.scale_keys, f), [cx, cy] = bd.center;
          for (const nm of [`ring${i}`, `badge${i}`, `txt${i}`]) {
            const n = parts[nm]; if (!n) continue;
            n.visible = s > 0.01; n.matrixAutoUpdate = false;
            const S = new THREE.Matrix4().makeTranslation(cx, cy, 0).multiply(new THREE.Matrix4().makeScale(s, s, 1))
              .multiply(new THREE.Matrix4().makeTranslation(-cx, -cy, 0));
            n.matrix.copy(S.multiply(base[nm]));
          }
        });
        cv.style.opacity = keyed(spec.opacity_keys, f);
        renderer.render(scene, cam);
        return true;
      },
    };
  }
  window.RM3D = { object, poseMatrix, keyed };
})();
