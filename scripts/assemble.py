"""Build the full reproduction from a manifest, then score it against the original.

Usage: python3 assemble.py <manifest.json> <out_dir> [--skip-render] [--brand brand.js]
manifest = {"source": "src.mp4", "end": 46.9667, "segments": [
   {"id": "S01-S03", "kind": "scene", "html": "scenes/pilot.html", "start": 0, "end": 5.0667},
   {"id": "S05", "kind": "layer", "html": "scenes/s05.html", "start": 8.5, "end": 11.1667},   # transparent, drawn on top
   {"id": "S09-S13", "kind": "extract", "start": 20.8, "end": 26.8333, "reason": "..."}, ...]}
Optional "objects_3d": path of the 3D inventory (default analysis/objects_3d.json), copied into the report.
Paths are relative to the manifest. Writes out_dir/reproduction.mp4 (with the source audio),
out_dir/side_by_side.mp4 and out_dir/report.json (SSIM / Delta E per segment).
With --brand: every scene is rendered with the brand file (colours, texts), extracted segments are
recoloured with the same palette (recolor.py), and the report checks the RHYTHM against the original
(rhythm.py: every movement on the same frame) instead of pixel similarity.
"""
import sys, os, json, subprocess
import numpy as np
import cv2

COLOR_DE = 10.0  # Delta E (95th percentile of a frame) above which the colours are listed as wrong
GHOST_PX = 600  # clustered extra / missing edge pixels in a frame above which it is listed for review

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rmcommon  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
RENDER = os.path.join(HERE, '..', 'engine', 'render.mjs')


def run(cmd):
    print('$', ' '.join(cmd[:6]), '...', flush=True)
    subprocess.run(cmd, check=True)


def main():
    man_path, out = sys.argv[1], sys.argv[2]
    skip = '--skip-render' in sys.argv
    brand = rmcommon.arg(sys.argv, 'brand')
    brand = os.path.abspath(brand) if brand else None
    base = os.path.dirname(os.path.abspath(man_path))
    man = json.load(open(man_path))
    src = os.path.join(base, man['source'])
    V = rmcommon.probe(src); fps = man.get('fps', V['fps'])  # frame rate and size of the source, never constants
    if 'end' not in man:
        man['end'] = V['frames'] / fps
    size = ['--fps', f'{fps:g}', '--w', str(man.get('w', V['w'])), '--h', str(man.get('h', V['h']))] + (['--brand', brand] if brand else [])
    os.makedirs(out, exist_ok=True)
    layers = []
    for s in man['segments']:
        tag = s['id'].replace(' ', '_')
        if s['kind'] == 'extract':
            path = os.path.join(out, f'{tag}.mp4')
            if not skip:
                # frame-accurate cut: select by frame number (a time seek can land one frame off -> visible jump)
                fa, fb = round(s['start'] * fps), round(s['end'] * fps) - 1
                run(['ffmpeg', '-y', '-v', 'error', '-i', src, '-vf', f"select='between(n\\,{fa}\\,{fb})',setpts=N/({fps:g}*TB)",
                     '-an', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '10', '-pix_fmt', 'yuv420p', path])
                if brand:  # an extract is the original's pixels: recolour it with the same palette
                    run([sys.executable, '-I', os.path.join(HERE, 'recolor.py'), path, path + '.brand.mp4', brand])
                    os.replace(path + '.brand.mp4', path)
        elif s['kind'] == 'layer':
            path = os.path.join(out, f'{tag}_layer')
            if not skip:
                run(['node', RENDER, os.path.join(base, s['html']), path, '--start', str(s['start']), '--end', str(s['end']),
                     '--transparent', '--frames-dir', path, *size])
        else:
            path = os.path.join(out, f'{tag}.mp4')
            if not skip:
                run(['node', RENDER, os.path.join(base, s['html']), path, '--start', str(s['start']), '--end', str(s['end']), *size])
        layers.append(f"{path}:{s['start']}")
    final = os.path.join(out, 'reproduction.mp4')
    run([sys.executable, '-I', os.path.join(HERE, 'compose.py'), final, '0', str(man['end']), *layers, '--audio', src, '--fps', f'{fps:g}'])
    if brand:
        run([sys.executable, '-I', os.path.join(HERE, 'rhythm.py'), src, final, os.path.join(out, 'rhythm.json'), '--end', str(man['end'])])
        return
    cmp_dir = os.path.join(out, 'compare')
    run([sys.executable, '-I', os.path.join(HERE, 'compare.py'), src, final, '0', str(man['end']), cmp_dir, '--worst', '10'])
    rows = json.load(open(os.path.join(cmp_dir, 'metrics.json')))['rows']
    report = {'segments': []}
    for s in man['segments']:
        if s['kind'] == 'layer':
            continue
        r = [x for x in rows if s['start'] - 1e-6 <= x['t'] < s['end'] - 1e-6]
        if not r:
            continue
        ss = [x['ssim'] for x in r]
        report['segments'].append({'id': s['id'], 'kind': s['kind'], 'start': s['start'], 'end': s['end'],
                                   'ssim_mean': round(sum(ss) / len(ss), 4), 'ssim_min': round(min(ss), 4),
                                   'share_ge_098': round(sum(v >= 0.98 for v in ss) / len(ss), 3),
                                   'deltaE_mean': round(sum(x['deltaE_mean'] for x in r) / len(r), 3),
                                   'note': s.get('reason', '')})
    allr = [x['ssim'] for x in rows]
    rebuilt = [x['ssim'] for x in rows if not any(s['kind'] == 'extract' and s['start'] <= x['t'] < s['end'] for s in man['segments'])]
    report['overall'] = {'frames': len(allr), 'ssim_mean': round(sum(allr) / len(allr), 4),
                         'ssim_mean_rebuilt_only': round(sum(rebuilt) / len(rebuilt), 4),
                         'share_ge_098': round(sum(v >= 0.98 for v in allr) / len(allr), 3)}
    # anomaly detector: an isolated drop (frame much worse than its neighbours) = misaligned cut,
    # wrong frame or a one-frame glitch. Every segment boundary is also listed with its score.
    ss = [x['ssim'] for x in rows]; anomalies = []
    for i, v in enumerate(ss):
        nb = [ss[j] for j in range(max(0, i - 3), min(len(ss), i + 4)) if j != i]
        if nb and v < float(np.median(nb)) - 0.05:
            anomalies.append({'frame': i, 't': round(i / fps, 3), 'ssim': v, 'neighbours': round(float(np.median(nb)), 4)})
    report['anomalies'] = anomalies
    # ghost detector: runs of frames where the copy shows shapes the original does not have (doubled text,
    # element too early / too late). SSIM hides them (a few % of the frame). Every run must be looked at.
    def find_runs(key):
        v = [x.get(key, 0) for x in rows]; rr, s0 = [], None
        for i, x in enumerate(v + [0]):
            if x > GHOST_PX and s0 is None:
                s0 = i
            elif x <= GHOST_PX and s0 is not None:
                if i - s0 >= 2:
                    rr.append({'from': s0, 'to': i - 1, 't': round(s0 / fps, 2), 'peak_px': max(v[s0:i]), 'kind': key})
                s0 = None
        return rr, v
    runs, gp = find_runs('ghost_px')
    miss, mp = find_runs('missing_px')   # a letter or shape of the original missing in the copy (e.g. a plate hole)
    # wrong colours: SSIM is computed on grey levels and does not see a grey shown as lavender, beige as violet
    v = [x.get('deltaE_p95', 0) for x in rows]; col, s0 = [], None
    for i, x in enumerate(v + [0]):
        if x > COLOR_DE and s0 is None:
            s0 = i
        elif x <= COLOR_DE and s0 is not None:
            if i - s0 >= 2:
                col.append({'from': s0, 'to': i - 1, 't': round(s0 / fps, 2), 'peak_deltaE_p95': round(max(v[s0:i]), 1), 'kind': 'colour'})
            s0 = None
    report['colour_runs'] = col
    report['missing_runs'] = miss
    runs_all = sorted(runs + miss + col, key=lambda r: r['from'])
    report['ghost_runs'] = runs
    if runs_all:  # contact sheet of the worst frame of each run: original | copy
        co, cc = cv2.VideoCapture(src), cv2.VideoCapture(final); tiles = []
        for r in runs_all[:24]:
            v = gp if r['kind'] == 'ghost_px' else mp if r['kind'] == 'missing_px' else [x.get('deltaE_p95', 0) for x in rows]
            f = r['from'] + int(np.argmax(v[r['from']:r['to'] + 1]))
            co.set(cv2.CAP_PROP_POS_FRAMES, f); cc.set(cv2.CAP_PROP_POS_FRAMES, f)
            a_, b_ = co.read()[1], cc.read()[1]
            if a_ is None or b_ is None:
                continue
            t_ = np.hstack([a_, cv2.resize(b_, (a_.shape[1], a_.shape[0]))])
            cv2.putText(t_, f'{f / fps:.2f}s', (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            tiles.append(cv2.resize(t_, None, fx=0.5, fy=0.5))
        if tiles:
            cv2.imwrite(os.path.join(out, 'ghosts.png'), np.vstack(tiles))
    cuts = sorted({round(sg['start'] * fps) for sg in man['segments']} | {round(sg['end'] * fps) for sg in man['segments']})
    report['cuts'] = [{'frame': c, 'before': ss[c - 1] if 0 < c <= len(ss) else None, 'after': ss[c] if c < len(ss) else None} for c in cuts]
    # 3D objects (rule "objets 3D"): one row per inventoried object, with its own local score (object_score.py)
    inv = os.path.join(base, man.get('objects_3d', 'analysis/objects_3d.json'))
    if os.path.exists(inv):
        report['objects_3d'] = json.load(open(inv))
        for o in report['objects_3d']:
            print(f"  objet 3D {o['name']:16s} {o.get('status', '?'):28s} {o.get('score', '')}")
    json.dump(report, open(os.path.join(out, 'report.json'), 'w'), indent=1, ensure_ascii=False)
    print(f'{len(anomalies)} anomalies', [a['frame'] for a in anomalies][:40])
    print(f"{len(runs)} plages à fantômes possibles, {len(miss)} plages à éléments manquants, {len(col)} plages à couleurs fausses",
          [(r['t'], r['to'] - r['from'] + 1, r['kind']) for r in runs_all][:30], '-> ghosts.png' if runs_all else '')
    print(json.dumps(report['overall']))
    for s in report['segments']:
        print(f"{s['id']:10s} {s['kind']:8s} {s['start']:6.2f}-{s['end']:6.2f}  SSIM {s['ssim_mean']:.3f} (min {s['ssim_min']:.3f})  ΔE {s['deltaE_mean']:.2f}")


if __name__ == '__main__':
    main()
