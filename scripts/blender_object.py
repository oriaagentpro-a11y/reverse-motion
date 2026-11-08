"""Model a 3D object (icon, badge, coin, card...) in Blender and render it frame by frame on its measured pose.

Usage: python3 blender_object.py <object.json> <pose.json> <out_dir> [--frames 590-652] [--samples 48]
                                 [--calibrate video.mp4:3] [--glb out.glb] [--shutter 0.5] [--only-ref]
Uses Blender as a Python module (`pip install bpy`, see blender_setup.sh) or, if absent, re-launches itself
with a Blender executable found on the machine (`blender -b --python this.py -- args`). Method and pitfalls:
METHODS.md § 14 ; modelling, materials, light, render: BLENDER_GUIDE.md.

object.json (sizes in face widths: the front face is 1 wide, y up, centred, z towards the camera):
{
 "body":   {"w": 1, "h": 0.98, "depth": 0.18, "radius": 0.26, "bevel": 0.015, "bevel_segments": 6,
            "color": "#F4F6FA", "roughness": 0.6, "clearcoat": 0, "specular": 0.5, "grain": 0.1,
            "gradient": ["#top", "#bottom"], "sample": [[u, v], ...]},
 "glyphs": [{"rrects": [[x0, y0, x1, y1, r]], "polygons": [[[x, y], ...]], "polygon": [[x, y], ...],
             "color": "#2E5BE8", "depth": 0.012, "z": 0, "roughness": 0.6, "sample": [[u, v]]}],
             (all shapes of one glyph are fused by a boolean union: one solid, no seam)
 "badges": [{"center": [0.41, 0.41], "r": 0.186, "depth": 0.05, "color": "#0E1116", "roughness": 0.75,
             "specular": 0.15, "ring": {"color": "#1E51E0", "w": 0.022}, "text": "3", "text_color": "#FFFFFF",
             "font": "font.ttf (relative to object.json)", "text_size": 0.25,
             "scale_keys": {"611": 0, "612": 0.45, "617": 1.07, "625": 1}, "sample": [[u, v]]}],
 "world":  {"color": "#2A5BE6", "strength": 0.25},
 "lights": [{"type": "AREA", "pos": [-0.5, 3.5, 3.5], "energy": 260, "size": 4, "color": "#FFFFFF"}],
             (fixed to the object, aimed at it: key / fill / rim)
 "exposure": 0, "opacity_keys": {"590": 0.76, "593": 1}, "shutter": 0.5,
 "live": {"gain": 5.5, "ambient": 2.0}   (light gains of the Three.js version, engine/rm-3d.js)
}
--calibrate: renders the reference frame, compares every part's colour at its "sample" points with the video
  and corrects base colours and exposure (linear light), N times; writes object.calibrated.json (P36).
pose.json: output of fit_object_pose.py. Every pose becomes a keyframe -> Cycles motion blur (P37).
Writes out_dir/f_XXXXX.png (RGBA, full frame size, transparent around the object) for every posed frame:
the layer drawn by engine/rm-3d.js (mode "frames"), also usable by compose.py and as holes for extract_plate.py.
--glb also exports the model (glTF binary, Blender axes) + <out>.glb.js (base64 + spec, for file:// pages):
the same object rendered live and editable with Three.js (rm-3d.js, mode "live").
"""
import sys, os, json, math, subprocess, shutil

HERE = os.path.dirname(os.path.abspath(__file__))


def _relaunch():
    exe = os.environ.get('BLENDER_PATH') or shutil.which('blender')
    if not exe:
        sys.exit('Blender introuvable : lancez "bash scripts/blender_setup.sh" (pip install bpy) ou définissez BLENDER_PATH.')
    args = sys.argv[1:]
    sys.exit(subprocess.call([exe, '-b', '--factory-startup', '--python', os.path.abspath(__file__), '--'] + args))


try:
    import bpy  # noqa: F401
except ImportError:
    _relaunch()
import bpy
import bmesh
from mathutils import Matrix, Vector, Euler


def argv():
    a = sys.argv
    return a[a.index('--') + 1:] if '--' in a else a[1:]


def hexrgb(h):
    h = h.lstrip('#')
    s = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple((c / 12.92) if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in s) + (1.0,)   # sRGB -> linear


def set_input(node, names, value):
    """Principled BSDF inputs changed names across Blender versions: set the first one that exists (guide § 6.1)."""
    for n in names:
        if n in node.inputs:
            node.inputs[n].default_value = value
            return True
    return False


def material(name, P):
    """Principled material from a part's spec: color, roughness, clearcoat, specular (IOR level), metallic,
    grain (moulded-plastic micro-grain: noise -> bump + roughness variation, guide § 6.4 / 13),
    gradient ([top_hex, bottom_hex] on the face: baked studio fall-off seen on many icons)."""
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; b = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    b.inputs['Base Color'].default_value = hexrgb(P['color'])
    b.inputs['Roughness'].default_value = P.get('roughness', 0.5)
    set_input(b, ('Metallic',), P.get('metallic', 0.0))
    set_input(b, ('Coat Weight', 'Clearcoat'), P.get('clearcoat', 0.0))
    if 'specular' in P:
        set_input(b, ('Specular IOR Level', 'Specular'), P['specular'])
    if P.get('gradient'):
        tc = nt.nodes.new('ShaderNodeTexCoord'); sep = nt.nodes.new('ShaderNodeSeparateXYZ')
        mr = nt.nodes.new('ShaderNodeMapRange'); ramp = nt.nodes.new('ShaderNodeValToRGB')
        nt.links.new(tc.outputs['Object'], sep.inputs[0]); nt.links.new(sep.outputs['Y'], mr.inputs[0])
        h = P.get('h', 1.0) / 2; mr.inputs['From Min'].default_value = -h; mr.inputs['From Max'].default_value = h
        nt.links.new(mr.outputs[0], ramp.inputs[0])
        ramp.color_ramp.elements[0].color = hexrgb(P['gradient'][1]); ramp.color_ramp.elements[1].color = hexrgb(P['gradient'][0])
        nt.links.new(ramp.outputs['Color'], b.inputs['Base Color'])
    if P.get('grain'):
        tc = nt.nodes.new('ShaderNodeTexCoord'); nz = nt.nodes.new('ShaderNodeTexNoise')
        nz.inputs['Scale'].default_value = P.get('grain_scale', 400.0); nz.inputs['Detail'].default_value = 2.0
        nt.links.new(tc.outputs['Object'], nz.inputs['Vector'])
        bump = nt.nodes.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = P['grain']
        nt.links.new(nz.outputs['Fac'], bump.inputs['Height']); nt.links.new(bump.outputs['Normal'], b.inputs['Normal'])
    return m


def squircle_points(w, h, r, n=24):
    pts = []
    for cx, cy, a0 in ((w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90), (-w / 2 + r, -h / 2 + r, 180), (w / 2 - r, -h / 2 + r, 270)):
        for i in range(n + 1):
            t = math.radians(a0 + 90 * i / n)
            pts.append((cx + r * math.cos(t), cy + r * math.sin(t)))
    return pts


def prism(name, pts, z0, z1, mat):
    """Extruded polygon between z0 and z1 (front face at z1)."""
    me = bpy.data.meshes.new(name); bm = bmesh.new()
    bot = [bm.verts.new((x, y, z0)) for x, y in pts]
    top = [bm.verts.new((x, y, z1)) for x, y in pts]
    bm.faces.new(top); bm.faces.new(list(reversed(bot)))
    n = len(pts)
    for i in range(n):
        bm.faces.new((bot[i], bot[(i + 1) % n], top[(i + 1) % n], top[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); ob.data.materials.append(mat)
    return ob


def build(spec, root):
    col = bpy.context.scene.collection
    B = spec['body']; w, h, d = B.get('w', 1), B.get('h', 1), B.get('depth', 0.3)
    body = prism('body', squircle_points(w, h, B.get('radius', 0.22) * w), -d, 0.0,
                 material('body', dict(B, h=h)))
    if B.get('bevel'):
        bv = body.modifiers.new('bevel', 'BEVEL'); bv.width = B['bevel'] * w; bv.segments = B.get('bevel_segments', 8)
        bv.limit_method = 'ANGLE'; bv.profile = B.get('bevel_profile', 0.5)
    for p in body.data.polygons:
        p.use_smooth = True
    try:   # large flat faces stay flat, rounded edges stay smooth (guide § 4.4)
        body.modifiers.new('wn', 'WEIGHTED_NORMAL').keep_sharp = True
    except Exception:
        pass
    col.objects.link(body); body.parent = root
    for i, g in enumerate(spec.get('glyphs', [])):
        z = g.get('z', 0.0); dz = g.get('depth', 0.02); mat = material(f'glyph{i}', g)
        shapes = [g['polygon']] if 'polygon' in g else []
        for x0, y0, x1, y1, r in g.get('rrects', []):        # rounded rectangles (bubbles, buttons, cards)
            r = min(r, (x1 - x0) / 2, (y1 - y0) / 2)
            shapes.append([((x0 + x1) / 2 + px, (y0 + y1) / 2 + py) for px, py in squircle_points(x1 - x0, y1 - y0, r, 12)])
        shapes += g.get('polygons', [])
        main_ob = None
        for j, poly in enumerate(shapes):
            ob = prism(f'glyph{i}_{j}', [tuple(p) for p in poly], z - 0.005, z + dz, mat)
            col.objects.link(ob); ob.parent = root
            if main_ob is None:
                main_ob = ob
            else:   # one solid per glyph: boolean union (no seam, no z-fighting where shapes overlap; guide § 4.5)
                bo = main_ob.modifiers.new(f'u{j}', 'BOOLEAN'); bo.operation = 'UNION'; bo.object = ob
                bo.solver = 'EXACT' if 'EXACT' in [e.identifier for e in bo.bl_rna.properties['solver'].enum_items] else bo.solver
                ob.hide_render = True; ob.hide_viewport = True; ob.name = f'_op_glyph{i}_{j}'
    for i, bd in enumerate(spec.get('badges', [])):
        cx, cy = bd['center']; r = bd['r']; dz = bd.get('depth', 0.05); zb = bd.get('z', 0.02)
        circ = lambda rr, n=64: [(cx + rr * math.cos(2 * math.pi * k / n), cy + rr * math.sin(2 * math.pi * k / n)) for k in range(n)]
        if bd.get('ring'):
            ring = prism(f'ring{i}', circ(r), zb, zb + dz, material(f'ring{i}', dict({'roughness': 0.6}, **bd['ring']))); col.objects.link(ring); ring.parent = root
            r_in = r - bd['ring']['w']
        else:
            r_in = r
        disc = prism(f'badge{i}', circ(r_in), zb + 0.002, zb + dz + 0.004, material(f'badge{i}', bd))
        col.objects.link(disc); disc.parent = root
        if bd.get('text'):
            cu = bpy.data.curves.new(f'txt{i}', 'FONT'); cu.body = bd['text']; cu.align_x = 'CENTER'; cu.align_y = 'CENTER'
            if bd.get('font'):
                cu.font = bpy.data.fonts.load(os.path.join(spec.get('_dir', ''), bd['font']))   # relative to object.json
            cu.size = bd.get('text_size', r); cu.extrude = 0.004
            tc = bpy.data.objects.new(f'_txtcurve{i}', cu); col.objects.link(tc)
            # text as a real mesh (glTF exports meshes only: the badge text must exist in the live model too)
            me = bpy.data.meshes.new_from_object(tc.evaluated_get(bpy.context.evaluated_depsgraph_get()))
            bpy.data.objects.remove(tc)
            tx = bpy.data.objects.new(f'txt{i}', me); tx.location = (cx, cy, zb + dz + 0.006)
            tx.data.materials.clear()
            tx.data.materials.append(material(f'txt{i}', {'color': bd.get('text_color', '#FFFFFF'), 'roughness': 0.6, 'specular': 0.2}))
            col.objects.link(tx); tx.parent = root


def keyed(keys, f, default=1.0):
    """Linear interpolation in {frame: value} (values measured on the video, e.g. a badge popping in)."""
    if not keys:
        return default
    ks = sorted((int(k), v) for k, v in keys.items())
    if f <= ks[0][0]:
        return ks[0][1]
    for (f0, v0), (f1, v1) in zip(ks, ks[1:]):
        if f0 <= f <= f1:
            return v0 + (v1 - v0) * (f - f0) / max(1, f1 - f0)
    return ks[-1][1]


def anim(spec, f):
    """Parts with a "scale_keys" (a badge, a sticker) scale around their own centre on the object's face."""
    for i, bd in enumerate(spec.get('badges', [])):
        s = keyed(bd.get('scale_keys'), f)
        cx, cy = bd['center']
        for name in (f'ring{i}', f'badge{i}', f'txt{i}'):
            ob = bpy.data.objects.get(name)
            if ob is None:
                continue
            ob.hide_render = s <= 0.01
            if name.startswith('txt'):
                ob.scale = (s, s, 1); ob.location = (cx, cy, ob.location[2])   # mesh centred on its own origin
            else:   # meshes are built in face coordinates: scale around the badge centre
                ob.matrix_basis = Matrix.Translation((cx, cy, 0)) @ Matrix.Diagonal((s, s, 1, 1)) @ Matrix.Translation((-cx, -cy, 0))


def border(sc, pose, f):
    p = pose['frames'][str(f)]
    qx = [c[0] for c in p['quad']]; qy = [c[1] for c in p['quad']]; mg = 0.35 * (max(qx) - min(qx))
    sc.render.use_border = True; sc.render.use_crop_to_border = False
    sc.render.border_min_x = max(0.0, (min(qx) - mg) / pose['w']); sc.render.border_max_x = min(1.0, (max(qx) + mg) / pose['w'])
    sc.render.border_min_y = max(0.0, 1 - (max(qy) + mg) / pose['h']); sc.render.border_max_y = min(1.0, 1 - (min(qy) - mg) / pose['h'])


def place(root, pose, f, C):
    p = pose['frames'][str(f)]
    rx, ry, rz = [math.radians(v) for v in p['rot_deg']]
    Rbl = C @ Euler((rx, ry, rz), 'XYZ').to_matrix() @ C
    t = Vector(p['pos'])
    root.matrix_world = Matrix.Translation(Vector((t.x, -t.y, -t.z))) @ Rbl.to_4x4()


def face_to_px(pose, f, u, v):
    """Point of the object's front face (units: width 1, y up) -> pixel on frame f (box + homography)."""
    bx, by, bw, bh = pose['box']; oh = bh / bw
    x, y = bx + (u + 0.5) * bw, by + (oh / 2 - v) / oh * bh
    H = pose['frames'][str(f)]['H']
    X = H[0] * x + H[1] * y + H[2]; Y = H[3] * x + H[4] * y + H[5]; Z = H[6] * x + H[7] * y + H[8]
    return X / Z, Y / Z


def calibrate(spec, pose, arg, out, C, root, spec_path):
    """Materials sampled from the video (P36): render the reference frame, compare the colour of every part at its
    "sample" points with the video, correct the base colours (linear light) and the exposure, repeat.
    arg = "<video>:<iterations>". Writes <object>.calibrated.json next to object.json."""
    import cv2, numpy as np
    video, n = arg.rsplit(':', 1) if ':' in arg else (arg, 4)
    f = pose['ref']; cap = cv2.VideoCapture(video); cap.set(cv2.CAP_PROP_POS_FRAMES, f); ok, src = cap.read()
    parts = [('body', spec['body'], 'body')] + [(f'glyph{i}', g, f'glyph{i}') for i, g in enumerate(spec.get('glyphs', []))] \
        + [(f'badge{i}', b, f'badge{i}') for i, b in enumerate(spec.get('badges', []))] \
        + [(f'ring{i}', b['ring'], f'ring{i}') for i, b in enumerate(spec.get('badges', [])) if b.get('ring')]
    lin = lambda c: np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    srgb = lambda c: np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(np.maximum(c, 0), 1 / 2.4) - 0.055)
    def patch(img, x, y, r=3):
        x, y = int(round(x)), int(round(y)); return np.median(img[y - r:y + r + 1, x - r:x + r + 1, :3].reshape(-1, 3), 0)[::-1] / 255
    sc = bpy.context.scene; place(root, pose, f, C); border(sc, pose, f); anim(spec, f)
    for it in range(int(n)):
        sc.render.filepath = os.path.join(os.path.abspath(out), '_calib.png'); bpy.ops.render.render(write_still=True)
        ren = cv2.imread(sc.render.filepath, cv2.IMREAD_UNCHANGED)
        report = []
        for name, P, mat in parts:
            pts = P.get('sample')
            if not pts:
                continue
            tg = np.mean([patch(src, *face_to_px(pose, f, u, v)) for u, v in pts], 0)
            rd = np.mean([patch(ren, *face_to_px(pose, f, u, v)) for u, v in pts], 0)
            ratio = (lin(tg) + 1e-3) / (lin(rd) + 1e-3)
            base = lin(np.array([int(P['color'].lstrip('#')[i:i + 2], 16) / 255 for i in (0, 2, 4)]))
            new = np.where(base < 1e-4, lin(tg), base * ratio)   # a base at 0 cannot be scaled: start from the target
            if name == 'body' and new.max() > 1:      # white already at maximum: brighten the light instead
                k = new.max(); sc.view_settings.exposure += math.log2(k); spec['exposure'] = sc.view_settings.exposure; new = new / k
            new = np.clip(new, 0, 1); P['color'] = '#%02X%02X%02X' % tuple(int(round(v * 255)) for v in srgb(new))
            bsdf = bpy.data.materials[mat].node_tree.nodes['Principled BSDF']; bsdf.inputs['Base Color'].default_value = hexrgb(P['color'])
            report.append(f"{name} {'#%02X%02X%02X' % tuple(int(v * 255) for v in rd)}->{'#%02X%02X%02X' % tuple(int(v * 255) for v in tg)}")
        print(f'calibrage {it + 1}/{n} : ' + ', '.join(report))
    spec.pop('_dir', None)
    json.dump(spec, open(spec_path.replace('.json', '.calibrated.json'), 'w'), indent=1)
    spec['_dir'] = os.path.dirname(os.path.abspath(spec_path))


def main():
    a = argv()
    spec, pose, out = json.load(open(a[0])), json.load(open(a[1])), a[2]
    spec['_dir'] = os.path.dirname(os.path.abspath(a[0]))
    opt = lambda k, d=None: a[a.index('--' + k) + 1] if '--' + k in a else d
    os.makedirs(out, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'; sc.cycles.samples = int(opt('samples', 48))
    sc.cycles.use_denoising = True; sc.render.film_transparent = True
    sc.render.resolution_x, sc.render.resolution_y = pose['w'], pose['h']
    sc.render.image_settings.file_format = 'PNG'; sc.render.image_settings.color_mode = 'RGBA'
    sc.view_settings.view_transform = 'Standard'; sc.view_settings.exposure = spec.get('exposure', 0.0)
    world = bpy.data.worlds.new('w'); sc.world = world; world.use_nodes = True
    bg = world.node_tree.nodes['Background']
    bg.inputs['Color'].default_value = hexrgb(spec.get('world', {}).get('color', '#FFFFFF'))
    bg.inputs['Strength'].default_value = spec.get('world', {}).get('strength', 1.0)
    for i, L in enumerate(spec.get('lights', [])):
        ld = bpy.data.lights.new(f'L{i}', L.get('type', 'AREA')); ld.energy = L.get('energy', 300)
        ld.color = hexrgb(L.get('color', '#FFFFFF'))[:3]
        if ld.type == 'AREA':
            ld.size = L.get('size', 2)
        lo = bpy.data.objects.new(f'L{i}', ld); lo.location = L.get('pos', (-2, 3, 4)); sc.collection.objects.link(lo)
        lo.rotation_euler = (-Vector(lo.location)).to_track_quat('-Z', 'Y').to_euler()   # aimed at the object
    # camera at the origin looking down -Z (Blender), vertical fov from the pose measurement
    cam = bpy.data.cameras.new('cam'); cam.sensor_fit = 'VERTICAL'; cam.angle_y = math.radians(pose['fov'])
    co = bpy.data.objects.new('cam', cam); sc.collection.objects.link(co); sc.camera = co
    root = bpy.data.objects.new('root', None); sc.collection.objects.link(root)
    build(spec, root)
    # lights follow the object (studio light fixed relative to it, as in most icon renders)
    for o in sc.collection.objects:
        if o.type == 'LIGHT':
            o.parent = root
    if opt('glb'):
        # export_yup=False: glTF keeps Blender's object axes (face in x/y, z towards the camera) = rm-3d.js axes
        glb = os.path.abspath(opt('glb'))
        bpy.ops.export_scene.gltf(filepath=glb, export_format='GLB', use_selection=False, export_apply=True, export_yup=False, use_visible=True)
        import base64   # file:// pages cannot fetch a .glb: also written as a script (window.RM_GLB[name] = base64)
        name = os.path.splitext(os.path.basename(glb))[0]
        with open(glb + '.js', 'w') as fh:
            fh.write(f"(window.RM_GLB = window.RM_GLB || {{}})[{json.dumps(name)}] = '{base64.b64encode(open(glb, 'rb').read()).decode()}';\n")
            sp = {k: v for k, v in spec.items() if k != '_dir'}
            fh.write(f"(window.OBJ3D = window.OBJ3D || {{}})[{json.dumps(name)}] = {json.dumps(sp)};\n")
    C = Matrix(((1, 0, 0), (0, -1, 0), (0, 0, -1)))
    if opt('calibrate'):
        calibrate(spec, pose, opt('calibrate'), out, C, root, a[0])
    rng = opt('frames'); frames = sorted(int(f) for f in pose['frames'])
    if rng:
        lo_, hi_ = [int(v) for v in rng.split('-')]; frames = [f for f in frames if lo_ <= f <= hi_]
    if '--only-ref' in a:
        frames = [pose['ref']]
    # every measured pose (and part animation) becomes a keyframe: Cycles then renders the object's own
    # MOTION BLUR between frames, like the video (fast entrances are smeared, P37). --shutter 0 = off.
    shutter = float(opt('shutter', spec.get('shutter', 0.5)))
    root.rotation_mode = 'QUATERNION'; prev_q = None
    for f in sorted(int(k) for k in pose['frames']):
        place(root, pose, f, C)
        q = root.matrix_world.to_quaternion()
        if prev_q is not None and prev_q.dot(q) < 0:      # same rotation, continuous sign (no spin between keys)
            q.negate()
        root.rotation_quaternion = q; prev_q = q.copy()
        root.keyframe_insert('location', frame=f); root.keyframe_insert('rotation_quaternion', frame=f)
        anim(spec, f)
        for ob in sc.objects:
            if ob.parent == root and ob.type != 'LIGHT' and not ob.name.startswith('_op_'):
                ob.keyframe_insert('location', frame=f); ob.keyframe_insert('scale', frame=f); ob.keyframe_insert('hide_render', frame=f)
    for ob in list(sc.objects):
        ad = ob.animation_data
        if ad and ad.action:
            fcs = getattr(ad.action, 'fcurves', None)
            if fcs is None:   # Blender 4.4+/5: layered actions
                fcs = [fc for l in ad.action.layers for st in l.strips for cb in st.channelbags for fc in cb.fcurves]
            for fc in fcs:
                for kp in fc.keyframe_points:
                    kp.interpolation = 'LINEAR'
    sc.render.use_motion_blur = shutter > 0
    if shutter > 0:
        sc.render.motion_blur_shutter = shutter
    for f in frames:
        sc.frame_set(f)
        # render only around the object (border = its quad + margin): same full-size transparent PNG, much faster
        border(sc, pose, f)
        sc.render.filepath = os.path.join(os.path.abspath(out), f'f_{f:05d}.png')
        bpy.ops.render.render(write_still=True)
        op = keyed(spec.get('opacity_keys'), f)
        if op < 0.999:   # fade measured on the video (object = op * render + (1 - op) * background)
            import numpy as np, cv2
            im = cv2.imread(sc.render.filepath, cv2.IMREAD_UNCHANGED); im[..., 3] = (im[..., 3] * op).astype(np.uint8)
            cv2.imwrite(sc.render.filepath, im)
    print(f'{len(frames)} images rendues -> {out}')


if __name__ == '__main__':
    main()
