"""Music analysis: tempo, beats and strong accents of a video's soundtrack, as frame numbers.

Usage: python3 beats.py <video.mp4> <out.json> [--fps 30]
out.json = {"tempo": 120.0, "beats": [{"t": 0.52, "frame": 16, "strength": 0.81}, ...],
            "accents": [...the strongest onsets (top 25 %)...], "downbeats": [...every 4th beat from the strongest phase...]}
Use it to check that every cut and every element entrance of the copy lands on the same frame as in the
original (an entrance that is one frame late on an accent is visible), and, for a rebranded version with new
music, to snap the GSAP start times onto the new accents.
"""
import sys, os, json, subprocess, tempfile
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rmcommon  # noqa: E402


def main():
    video, out = sys.argv[1], sys.argv[2]
    fps = rmcommon.arg(sys.argv, 'fps', None, float) or rmcommon.probe(video)['fps']
    import librosa
    with tempfile.TemporaryDirectory() as td:
        wav = os.path.join(td, 'a.wav')
        r = subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', video, '-vn', '-ac', '1', '-ar', '22050', wav])
        if r.returncode or not os.path.exists(wav):
            sys.exit('pas de piste audio dans cette vidéo')
        y, sr = librosa.load(wav, sr=22050)
    env = librosa.onset.onset_strength(y=y, sr=sr)
    tempo, bf = librosa.beat.beat_track(onset_envelope=env, sr=sr)
    tempo = float(np.atleast_1d(tempo)[0])
    bt = librosa.frames_to_time(bf, sr=sr)
    if len(bt) > 8:  # slope of beat time vs index: finer than the estimator's tempo grid and the 23 ms hop
        tempo = 60.0 / float(np.polyfit(np.arange(len(bt)), bt, 1)[0])
    on = librosa.onset.onset_detect(onset_envelope=env, sr=sr, backtrack=False)
    peak = float(env.max()) or 1.0
    row = lambda f: {'t': round(float(librosa.frames_to_time(f, sr=sr)), 4),
                     'frame': int(round(float(librosa.frames_to_time(f, sr=sr)) * fps)),
                     'strength': round(float(env[f]) / peak, 3)}
    beats = [row(f) for f in bf]
    onsets = [row(f) for f in on]
    thr = float(np.percentile([o['strength'] for o in onsets], 75)) if onsets else 1
    accents = [o for o in onsets if o['strength'] >= thr]
    phase = max(range(4), key=lambda k: sum(b['strength'] for b in beats[k::4])) if len(beats) >= 4 else 0
    res = {'fps': fps, 'tempo': round(tempo, 2), 'beats': beats, 'accents': accents, 'downbeats': beats[phase::4]}
    json.dump(res, open(out, 'w'), indent=1)
    print(f"tempo {res['tempo']} BPM, {len(beats)} temps, {len(accents)} accents forts -> {out}")


if __name__ == '__main__':
    main()
