#!/usr/bin/env python3
"""Slice an isolated official-reference heap probe, never changing matrix evidence or grades."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile
import time

import matrix
from pandy_equiv import cases, runners, verify_settings
from run import outcome, plate_hashes
from yellow_diagnostics import measure

ENVIRONMENTS = {
    'normal': [],
    'fill85': ['MALLOC_PERTURB_=85'],
    'fill170': ['MALLOC_PERTURB_=170'],
    'no-tcache': ['GLIBC_TUNABLES=glibc.malloc.tcache_count=0'],
}


class HeapReference(runners.Reference):
    def __init__(self, mode):
        self.environment = ENVIRONMENTS[mode]

    def run(self, inputs, args, out_dir, timeout=1800):
        work = runners._prepare(inputs, out_dir)
        started = time.time()
        extra = [arg for value in self.environment for arg in ('-e', value)]
        process = subprocess.run([
            *runners.SUDO, 'docker', 'run', '--rm', '--network', 'none', *runners.pin(),
            '-v', f'{work}:/work', '-w', '/work', '-e', 'HOME=/work/home', '-e', 'LC_ALL=C',
            *extra, '--entrypoint', '/opt/bambu-studio/AppRun', runners.REFERENCE_IMAGE,
            *args, '--outputdir', '/work/out',
        ], capture_output=True, text=True, timeout=timeout)
        return runners._finish(work, out_dir, process, started)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', required=True, help='matrix key, e.g. gear|walls 4')
    parser.add_argument('--mode', choices=ENVIRONMENTS, default='fill85')
    parser.add_argument('--runs', type=int, default=3)
    parser.add_argument('--layer', type=int, help='optional zero-based layer to measure')
    parser.add_argument('--feature', default='Floating vertical shell')
    args = parser.parse_args()
    if args.runs < 1:
        parser.error('--runs must be positive')
    record = json.loads((matrix.OUT / 'results.json').read_text())[args.case]
    base = matrix.OUT / 'cells' / record['case']
    case = json.loads((base / 'inputs/case.json').read_text())
    if cases.case_id(case) != record['case']:
        raise ValueError('Cached input identity differs')
    runner = HeapReference(args.mode)
    if runner.describe()['image_id'] != record['reference_image']:
        raise ValueError('Official image differs from recorded reference')
    destination = matrix.ROOT / 'build/heap-probes'
    destination.mkdir(exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix=f"{record['case']}-{args.mode}-", dir=destination))
    argv = cases.materialise(case, root / 'inputs')
    phone = base / 'phone/out.gcode.3mf'
    for n in range(args.runs):
        runners.set_cpu(2)
        out = root / str(n)
        run = runner.run(root / 'inputs', argv, out)
        result = outcome(out, run.returncode, root / 'inputs', case)
        (out / 'run.json').write_text(json.dumps(result))
        if not result['sliced'] or result.get('profile_errors'):
            raise RuntimeError(f'Invalid diagnostic slice: {result}')
        errors = verify_settings.compare_outputs(out / 'out.gcode.3mf', phone)
        if errors:
            raise ValueError(errors)
        report = {'case': args.case, 'reference_image': record['reference_image'],
                  'environment': runner.environment, 'run': n, 'directory': str(out),
                  'plate_hashes': plate_hashes(out / 'out.gcode.3mf'),
                  'phone_byte_match': plate_hashes(phone) == plate_hashes(out / 'out.gcode.3mf')}
        if args.layer is not None:
            machine = json.loads((root / 'inputs/machine.json').read_text())
            nozzles = machine['nozzle_diameter']
            if not isinstance(nozzles, list):
                nozzles = [nozzles]
            gap = .15 * min(map(float, nozzles)) if args.feature == 'Floating vertical shell' else matrix.seam_gap(phone)
            report['measurement'] = measure(phone, out / 'out.gcode.3mf', args.layer, args.feature, gap)
        (out / 'probe.json').write_text(json.dumps(report, indent=2))
        print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
