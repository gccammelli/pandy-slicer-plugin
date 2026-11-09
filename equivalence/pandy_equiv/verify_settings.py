"""Check that successful slices actually use the requested profiles and settings."""
import json
import zipfile
from decimal import Decimal, InvalidOperation
from pathlib import Path


def _values(value):
    return value if isinstance(value, list) else [value]


def _same(a, b):
    a, b = str(a).strip(), str(b).strip()
    if a == b:
        return True
    if a.endswith('%') != b.endswith('%'):
        return False
    try:
        return Decimal(a.rstrip('%')) == Decimal(b.rstrip('%'))
    except InvalidOperation:
        return False


def compare_outputs(reference: Path, candidate: Path) -> list[str]:
    """Require the complete effective configuration to agree, not just selected sentinel settings."""
    try:
        def read(path):
            with zipfile.ZipFile(path) as z:
                value = json.loads(z.read('Metadata/project_settings.config'))
                if not isinstance(value, dict):
                    raise ValueError('project settings are not an object')
                return value
        left, right = read(reference), read(candidate)
        missing = object()
        differing = [key for key in sorted(left.keys() | right.keys()) if left.get(key, missing) != right.get(key, missing)]
        return [f'effective settings differ: {key}' for key in differing[:100]]
    except (OSError, KeyError, ValueError, zipfile.BadZipFile) as e:
        return [f'cannot compare effective settings: {e}']


def verify(output: Path, inputs: Path, case: dict) -> list[str]:
    try:
        with zipfile.ZipFile(output) as z:
            if not any(n.startswith('Metadata/plate_') and n.endswith('.gcode') for n in z.namelist()):
                return ['output contains no sliced plate']
            actual = json.loads(z.read('Metadata/project_settings.config'))
            if not isinstance(actual, dict):
                raise ValueError('project settings are not an object')
        machine = json.loads((inputs / 'machine.json').read_text())
        process = json.loads((inputs / 'process.json').read_text())
        filaments = [json.loads((inputs / f'filament{i + 1}.json').read_text()) for i in range(len(case['filaments']))]
    except (OSError, KeyError, ValueError, zipfile.BadZipFile) as e:
        return [f'cannot read effective settings: {e}']

    errors = []
    def check(key, expected, index=0):
        got = _values(actual[key]) if key in actual else []
        want = _values(expected)
        if not want or index >= len(got) or not _same(want[0], got[index]):
            errors.append(f'{key}[{index}] expected {want[0] if want else "<empty>"!r}, got {got[index] if index < len(got) else "<missing>"!r}')

    for key in ('printer_model',):
        if key not in machine:
            errors.append(f'machine profile lacks {key}')
        else:
            check(key, machine[key])
    for key in set(('layer_height', 'wall_loops', 'sparse_infill_density', 'outer_wall_speed')) | set(case['process_overrides']):
        if key not in process:
            errors.append(f'process profile lacks {key}')
        else:
            expected = process[key]
            if key in case['process_overrides'] and isinstance(expected, list):
                for i, item in enumerate(expected):
                    check(key, item, i)
            else:
                check(key, expected)
    for i, filament in enumerate(filaments):
        for key in set(('filament_max_volumetric_speed', 'filament_density')) | set(case['filament_overrides']):
            if key not in filament:
                errors.append(f'filament profile lacks {key}')
            elif key in case['filament_overrides'] and isinstance(filament[key], list) and len(filament[key]) > 1:
                if len(filaments) > 1:
                    errors.append(f'cannot verify multi-value {key} across multiple filaments')
                else:
                    for n, item in enumerate(filament[key]):
                        check(key, item, n)
            else:
                check(key, filament[key], i)
    return errors
