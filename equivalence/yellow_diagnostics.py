#!/usr/bin/env python3
"""Read-only diagnostics of a saved matrix cell; contour completion never changes its grade."""
import argparse
from collections import Counter
import json
import zipfile

import matrix
from pandy_equiv import cases


def measure(candidate, reference, layer, feature, gap):
    a, e = matrix.paths(candidate)[layer][feature]
    b, er = matrix.paths(reference)[layer][feature]
    ac, ag = a.close_seams(gap + .002, max(0., gap - .002))
    bc, bg = b.close_seams(gap + .002, max(0., gap - .002))
    return {
        'layer_index_zero_based': layer, 'feature': feature,
        'raw_distance_mm': matrix.max_dist(a, b),
        'completed_distance_mm_diagnostic_only': matrix.max_dist(ac, bc),
        'closed_gaps_mm': {'phone': ag, 'reference': bg},
        'filament_mm': {'phone': e, 'reference': er},
        'filament_change_percent': 100 * (e / er - 1) if er else None,
        'bounds_delta_mm': float(max(abs(a.min() - b.min()).max(), abs(a.max() - b.max()).max())),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', help='saved matrix key, e.g. cube|layer 0.24 mm')
    parser.add_argument('--layer', type=int, help='zero-based layer index')
    parser.add_argument('--feature', default='Floating vertical shell')
    parser.add_argument('--reference', type=int, default=0)
    args = parser.parse_args()
    records = json.loads((matrix.OUT / 'results.json').read_text())
    options = {(row, label): (row, label, kw) for row in matrix.ROWS for label, _, kw in matrix.columns()}
    current = [r for r in records.values()
               if (r['row'], r['column']) in options
               and r.get('classification_version') == matrix.CLASSIFICATION_VERSION
               and r.get('validation_sha256') == matrix.validation_hash()]
    yellow = [r for r in current if r['status'] == 'yellow']
    result = {'yellow_cells': len(yellow), 'by_model': dict(Counter(r['row'] for r in yellow)),
              'by_reported_features': dict(Counter(', '.join(r['detail']['features']) for r in yellow)),
              'cells_with_recognized_wall_seam_changes': sum(bool(r['detail'].get('seam_differences')) for r in yellow)}
    if args.case:
        if args.layer is None:
            parser.error('--case requires --layer')
        r = records[args.case]
        if r not in current:
            raise ValueError('Saved classification is stale or outside the current matrix')
        item = options[(r['row'], r['column'])]
        if r['case'] != matrix.cell_case(item[0], item[2])['id']:
            raise ValueError('Saved case does not match current matrix inputs')
        if not 0 <= args.reference < r['reference_runs']:
            raise ValueError('Reference index is outside recorded runs')
        base = matrix.OUT / 'cells' / r['case']
        case = json.loads((base / 'inputs/case.json').read_text())
        if cases.case_id(case) != r['case']:
            raise ValueError('Cached input identity differs')
        import hashlib
        ref_key = hashlib.sha256(r['reference_image'].encode()).hexdigest()[:16]
        ref = base / f'ref-{ref_key}-{args.reference}/out.gcode.3mf'
        candidate = base / 'phone/out.gcode.3mf'
        with zipfile.ZipFile(candidate) as z:
            cfg = json.loads(z.read('Metadata/project_settings.config'))
        nozzles = cfg['nozzle_diameter']
        if not isinstance(nozzles, list):
            nozzles = [nozzles]
        # Fill.cpp: loop clipping is 0.15 times nozzle diameter. This completion
        # is exploratory; material and local line widths can still differ.
        gap = .15 * min(map(float, nozzles)) if args.feature == 'Floating vertical shell' else matrix.seam_gap(candidate)
        result['measurement'] = measure(candidate, ref, args.layer, args.feature, gap)
        result['measurement'].update(case=args.case, reference_index=args.reference, assumed_gap_mm=gap)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
