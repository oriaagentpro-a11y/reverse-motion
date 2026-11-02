"""Fit a GSAP tween (ease, start, duration, from, to) to a measured time series.

Library use:  from fit_easing import fit;  fit(times, values) -> dict
CLI use:      python3 fit_easing.py '<json [[t, v], ...]>'
Searches every standard GSAP ease, the start time and the duration on a grid,
solves from/to by least squares, and returns the best fit with its error in the
measurement's own units (pixels, degrees, opacity...).
"""
import sys, json, math
import numpy as np


def _back(s=1.70158):
    return lambda p: p * p * ((s + 1) * p - s)


def _in(name):
    if name.startswith('power'):
        k = int(name[5]) + 1
        return lambda p: p ** k
    return {
        'sine': lambda p: 1 - np.cos(p * math.pi / 2),
        'expo': lambda p: np.where(p == 0, 0, 2 ** (10 * (p - 1))),
        'circ': lambda p: 1 - np.sqrt(np.clip(1 - p * p, 0, 1)),
        'back': _back(),
    }[name]


def ease(name):
    """name like 'power3.out', 'expo.inOut', 'none'."""
    if name == 'none':
        return lambda p: p
    base, kind = name.split('.')
    f = _in(base)
    if kind == 'in':
        return f
    if kind == 'out':
        return lambda p: 1 - f(1 - p)
    return lambda p: np.where(p < 0.5, f(2 * p) / 2, 1 - f(2 * (1 - p)) / 2)


EASES = ['none'] + [f'{b}.{k}' for b in ['power1', 'power2', 'power3', 'power4', 'sine', 'expo', 'circ', 'back']
                    for k in ['in', 'out', 'inOut']]


def fit(times, values, fps=30):
    t = np.asarray(times, float); v = np.asarray(values, float)
    span = t[-1] - t[0]
    step = 1 / fps
    best = None
    starts = np.arange(t[0] - 2 * step, t[0] + span * 0.5 + step / 2, step)
    for name in EASES:
        e = ease(name)
        for s in starts:
            for d in np.arange(2 * step, t[-1] - s + 2 * step + step / 2, step):
                p = np.clip((t - s) / d, 0, 1)
                y = e(p)
                A = np.stack([1 - y, y], 1)
                coef, *_ = np.linalg.lstsq(A, v, rcond=None)
                err = float(np.sqrt(np.mean((A @ coef - v) ** 2)))
                if best is None or err < best['rmse'] - 1e-9:
                    best = {'ease': name, 'start': round(float(s), 4), 'duration': round(float(d), 4),
                            'from': round(float(coef[0]), 3), 'to': round(float(coef[1]), 3),
                            'rmse': round(err, 4)}
    return best


if __name__ == '__main__':
    data = json.loads(sys.argv[1])
    print(json.dumps(fit([r[0] for r in data], [r[1] for r in data])))
