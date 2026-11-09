#!/usr/bin/env python3
"""Diagnostic fuzzy-skin statistics for the rectangular cube; does not award a pass.

Run from any directory: fuzzy_stats.py [--matrix build/matrix] [--step 0.05]
Statistics are length-weighted signed distances to the smooth official rectangle.
This intentionally does not generalize the rectangle test to arbitrary models.
"""
import argparse
import json
import math
from pathlib import Path
import numpy as np
from pandy_equiv import toolpaths


def signed_rectangle_distance(points, lo, hi):
    outside = np.linalg.norm(np.maximum(np.maximum(lo - points, points - hi), 0), axis=1)
    inside = np.minimum(points - lo, hi - points).min(axis=1)
    return np.where(inside >= 0, -inside, outside)


def statistics(data, smooth, step=.05):
    if not math.isfinite(step) or step <= 0: raise ValueError('step must be finite and positive')
    values, weights, means = [], [], []
    for layer in sorted(set(data) & set(smooth)):
        if layer < 1 or 'Outer wall' not in data[layer]: continue
        base = smooth[layer]['Outer wall'][0]
        lo, hi = base.min(), base.max()
        # Reject a curved/non-rectangular baseline rather than misinterpreting its bounding box.
        if any(p.center is not None for p in base.primitives):
            raise ValueError('This diagnostic requires a rectangular outer-wall baseline')
        check = np.concatenate([p.points(np.array([0., .5, 1.])) for p in base.primitives])
        if np.max(np.abs(signed_rectangle_distance(check, lo, hi))) > .001:
            raise ValueError('This diagnostic requires a rectangular outer-wall baseline')
        points, ws = [], []
        for p in data[layer]['Outer wall'][0].primitives:
            n = max(1, math.ceil(p.length / step))
            points.append(p.points((np.arange(n) + .5) / n))
            ws.append(np.full(n, p.length / n))
        signed = signed_rectangle_distance(np.concatenate(points), lo, hi)
        w = np.concatenate(ws)
        values.append(signed); weights.append(w)
        means.append(float(np.average(signed, weights=w)))
    if not values: raise ValueError('No matching layers to analyse')
    v, w = np.concatenate(values), np.concatenate(weights)
    mean = float(np.average(v, weights=w))
    return {'mean_signed_mm': mean, 'std_mm': float(np.sqrt(np.average((v - mean)**2, weights=w))),
            'max_abs_mm': float(np.abs(v).max()), 'layer_mean_range_mm': [min(means), max(means)], 'samples': len(v)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--matrix', type=Path, default=Path(__file__).resolve().parents[1] / 'build/matrix')
    parser.add_argument('--step', type=float, default=.05)
    args = parser.parse_args()
    results = json.loads((args.matrix / 'results.json').read_text())
    baseline, fuzzy = results['cube|baseline'], results['cube|fuzzy skin']
    base = args.matrix / 'cells' / baseline['case']
    work = args.matrix / 'cells' / fuzzy['case']
    references = sorted(work.glob('ref-*/out.gcode.3mf'))[:5]
    smooth = toolpaths.parse(next(base.glob('ref-*-0/out.gcode.3mf')))
    runs = [('phone', work / 'phone/out.gcode.3mf'), *((f'official-{i}', p) for i, p in enumerate(references))]
    print(json.dumps({'diagnostic_only': True, 'model': 'cube', 'baseline_case': baseline['case'],
                      'fuzzy_case': fuzzy['case'], 'step_mm': args.step, 'engine': fuzzy['engine'],
                      'runs': [{'run': name, **statistics(toolpaths.parse(path), smooth, args.step)} for name, path in runs]}, indent=2))


if __name__ == '__main__': main()
