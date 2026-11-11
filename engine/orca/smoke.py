#!/usr/bin/env python3
"""Run reproducible Orca editor jobs; no printer connection or print commands.

Run in pandy-studio-build with this checkout mounted at /repo. Reference and
candidate receive identical preset bytes and registry preparation. Only Orca's
G-code generation timestamp is normalized; raw hashes are retained in the report.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'equivalence'))
from pandy_equiv import cases, compare, profiles, safety

X1C = ('Bambu Lab X1 Carbon 0.4 nozzle', '0.20mm Standard @BBL X1C', 'Bambu PLA Basic @BBL X1C')
A1 = ('Bambu Lab A1 0.4 nozzle', '0.20mm Standard @BBL A1', 'Bambu PLA Basic @BBL A1')
FEATURES = ('overhangs', 'bridge', 'tube', 'thin')
# name: (printer, process, first filament), models, process overrides, further filaments
CASES = {
    'cube': (X1C, ('cube',), {}, ()),
    'benchy': (X1C, ('benchy',), {}, ()),
    'gear': (X1C, ('gear',), {}, ()),
    'a1': (A1, ('cube',), {}, ()),
    'features': (X1C, FEATURES, {}, ()),
    'objects': (X1C, ('cube', 'cylinder', 'sphere', 'torus', 'gear'), {}, ()),
    'tree': (X1C, ('sphere',), {'enable_support': '1', 'support_type': 'tree(auto)'}, ()),
    'supports': (X1C, ('overhangs',), {'enable_support': '1', 'support_type': 'normal(auto)'}, ()),
    'classic': (X1C, ('cylinder',), {'wall_generator': 'classic'}, ()),
    'gyroid': (X1C, ('tube',), {'sparse_infill_pattern': 'gyroid', 'sparse_infill_density': '25%'}, ()),
    'ironing': (X1C, ('sphere',), {'ironing_type': 'top'}, ()),
    'vase': (A1, ('cube',), {'spiral_mode': '1', 'wall_loops': '1', 'top_shell_layers': '0', 'sparse_infill_density': '0%'}, ()),
    'sequential': (X1C, ('cube', 'cube', 'cube'), {'print_sequence': 'by object'}, ()),
    'two-filaments': (X1C, ('cube', 'cylinder'), {}, ('Bambu PETG HF @BBL X1C',)),
    'a1-mini': (('Bambu Lab A1 mini 0.4 nozzle', '0.20mm Standard @BBL A1M', 'Bambu PLA Basic @BBL A1M'), FEATURES, {}, ()),
    'p1s': (('Bambu Lab P1S 0.4 nozzle', '0.20mm Standard @BBL X1C', 'Bambu PLA Basic @BBL X1C'), FEATURES, {}, ()),
    'h2d': (('Bambu Lab H2D 0.4 nozzle', '0.20mm Standard @BBL H2D', 'Bambu PLA Basic @BBL H2D'), FEATURES, {}, ()),
}
QUICK = ['cube', 'benchy', 'gear', 'a1']

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('runner', choices=('reference', 'engine', 'arm64'),
                    help='arm64 runs the phone build under qemu-aarch64-static, if the container has it')
parser.add_argument('--case', choices=sorted(CASES), action='append', dest='cases')
parser.add_argument('--all', action='store_true', help='every case rather than the four quick ones')
parser.add_argument('--unpinned', action='store_true', help='use every CPU instead of one (compare with the pinned reference)')
args = parser.parse_args()
lock = json.loads((ROOT / 'engine/orca/source.json').read_text())
library = profiles.Presets(ROOT / 'third_party/orcaslicer/resources')
cases.preset_library = lambda: library
base = ROOT / 'build/orca'
reference = base / 'reference/squashfs-root'
candidate = args.runner != 'reference'
if candidate:
    arch = 'x86_64' if args.runner == 'engine' else 'aarch64'
    package = base / arch / 'package'
    (package / 'bin').mkdir(parents=True, exist_ok=True)
    shutil.copy2(base / arch / 'engine/pandy-engine', package / 'bin/pandy-engine')
    if not (package / 'resources').exists():
        (package / 'resources').symlink_to(reference / 'resources', target_is_directory=True)
    command = [*(['qemu-aarch64-static'] if arch == 'aarch64' else []), str(package / 'bin/pandy-engine')]
else:
    command = [str(reference / 'AppRun')]

report = {}
for name in args.cases or (list(CASES) if args.all else QUICK):
    folder = base / 'smoke' / name
    inputs = folder / 'input'
    if candidate and not (folder / 'reference/out.gcode.3mf').is_file():
        raise SystemExit(f'Run the official reference first: {name}')
    selected, models, overrides, more_filaments = CASES[name]
    spacing = 36.0 if len(models) > 4 else 45.0
    case = dict(printer=selected[0], process=selected[1], filaments=[selected[2], *more_filaments],
                objects=cases.plate(*models, spacing=spacing), process_overrides=overrides, filament_overrides={}, args=['--strict'])
    if inputs.exists():
        shutil.rmtree(inputs)
    cli = cases.materialise(case, inputs)
    # Orca's user-preset registry requires a version. Keep the inheritance chain
    # and all resolved overrides intact rather than dropping the parent name.
    for path in inputs.glob('*.json'):
        if path.name == 'case.json':
            continue
        preset = json.loads(path.read_text())
        preset['version'] = lock['tag'].removeprefix('v')
        path.write_text(json.dumps(preset, indent=1))
    output = folder / args.runner
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    home = output / 'home'
    home.mkdir()
    data = home / 'data'
    system = data / 'system'
    system.mkdir(parents=True)
    for cache in (reference / 'resources/profiles').glob('*.opc'):
        shutil.copy2(cache, system / cache.name)
    for filename, kind, preset_name in [('machine.json', 'machine', 'case printer'),
                                       ('process.json', 'process', 'case process'),
                                       *((f'filament{i}.json', 'filament', f'case filament {i}') for i in range(1, len(case['filaments']) + 1))]:
        link = data / 'user/default' / kind / (preset_name + '.json')
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(inputs / filename)
    runtime = home / 'runtime'
    runtime.mkdir(mode=0o700)
    env = dict(os.environ, HOME=str(home), LC_ALL='C', XDG_RUNTIME_DIR=str(runtime))
    start = time.monotonic()
    cpu = min(os.sched_getaffinity(0))
    with (output / 'slice.log').open('w') as log:
        run = subprocess.run([*([] if args.unpinned else ['taskset', '-c', str(cpu)]), *command, *cli, '--datadir', str(data), '--outputdir', str(output)],
                             cwd=inputs, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=3600)
    result_path = output / 'result.json'
    result = json.loads(result_path.read_text()) if result_path.exists() else {}
    file = output / 'out.gcode.3mf'
    entry = dict(exit_code=run.returncode, seconds=round(time.monotonic() - start, 2), result=result,
                 input_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(inputs.iterdir()) if p.is_file()})
    entry['ok'] = run.returncode == 0 and result.get('return_code') == 0 and result.get('warnings') == [] and file.is_file()
    if entry['ok']:
        entry['safety_problems'] = safety.problems(file)
        entry['ok'] = not entry['safety_problems']
        with zipfile.ZipFile(file) as z:
            plates = {n: z.read(n) for n in z.namelist() if compare.GCODE.fullmatch(n)}
            entry['raw_gcode_sha256'] = {n: hashlib.sha256(b).hexdigest() for n, b in plates.items()}
            entry['md5_verified'] = bool(plates) and all(hashlib.md5(b).hexdigest().upper() == z.read(n + '.md5').decode().strip().upper() for n, b in plates.items())
            entry['ok'] &= entry['md5_verified']
        if candidate and (folder / 'reference/out.gcode.3mf').exists():
            ref = compare.read(folder / 'reference/out.gcode.3mf')
            expected = {n: b for n, b in ref.items() if compare.GCODE.fullmatch(n)}
            def normalize(b):
                return re.sub(rb'(?m)^; generated by OrcaSlicer ([^\r\n]+?) on \d{4}-\d{2}-\d{2} at \d{2}:\d{2}:\d{2}\r?$', rb'; generated by OrcaSlicer \1 on <timestamp>', b)
            entry['gcode_identical_except_timestamp'] = expected.keys() == plates.keys() and all(normalize(b) == normalize(plates[n]) for n, b in expected.items())
            entry['differences'] = {n: compare.first_difference(normalize(b), normalize(plates.get(n, b''))) for n, b in expected.items() if normalize(b) != normalize(plates.get(n, b''))}
    report[name] = entry
    (output / 'validation.json').write_text(json.dumps(entry, indent=2) + '\n')
    print(name, json.dumps({k: v for k, v in entry.items() if k not in ('input_sha256', 'result')}), flush=True)
summary = base / f'{args.runner}-smoke.json'
previous = json.loads(summary.read_text()) if summary.exists() else {}
summary.write_text(json.dumps({**previous, **report}, indent=2) + '\n')
if not all(v['ok'] and (not candidate or v.get('gcode_identical_except_timestamp')) for v in report.values()):
    raise SystemExit(1)
