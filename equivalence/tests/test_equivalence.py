import hashlib
import json
import math
import struct
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import matrix
from pandy_equiv import cases, models, profiles, verify_settings


class FakePresets:
    def resolve(self, name):
        return {
            'M': {'printer_model': 'X1', 'machine_start_gcode': 'G28\nG29'},
            'P': {'layer_height': '0.2', 'wall_loops': '2', 'outer_wall_speed': ['200'],
                  'sparse_infill_density': '15%', 'post_process': ['danger']},
            'F': {'filament_density': ['1.26'], 'filament_max_volumetric_speed': ['21'], 'filament_id': 'PLA'},
        }[name].copy()


def example():
    return {'printer': 'M', 'process': 'P', 'filaments': ['F'], 'objects': cases.plate('cube'),
            'process_overrides': {'wall_loops': '3'}, 'filament_overrides': {}, 'args': [], 'note': 'fixture'}


class EquivalenceTests(unittest.TestCase):
    def test_materialise_resolves_and_applies_overrides(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(cases, 'preset_library', return_value=FakePresets()):
            c = example(); c['id'] = cases.case_id(c)
            p = Path(tmp); cases.materialise(c, p)
            machine = json.loads((p / 'machine.json').read_text())
            process = json.loads((p / 'process.json').read_text())
            filament = json.loads((p / 'filament1.json').read_text())
            self.assertEqual(machine['printer_model'], 'X1')
            self.assertEqual(process['outer_wall_speed'], ['200'])
            self.assertEqual(process['wall_loops'], '3')
            self.assertNotIn('post_process', process)
            self.assertEqual(filament['filament_max_volumetric_speed'], ['21'])
            self.assertEqual(filament['filament_id'], 'PLA')
            self.assertEqual(process['inherits'], 'P')
            fixture = json.loads((Path(__file__).resolve().parents[2] / 'shared/src/androidUnitTest/resources/resolved-job-parity.json').read_text())
            self.assertEqual(fixture, {'machine.json': machine, 'process.json': process, 'filament1.json': filament})
            changed = example(); changed['process_overrides'] = {'wall_loops': '4'}
            self.assertNotEqual(c['id'], cases.case_id(changed))
            with self.assertRaises(ValueError):
                cases.materialise({**c, 'process_overrides': {'post_process': 'bad'}}, p)

    def test_success_must_contain_effective_settings(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(cases, 'preset_library', return_value=FakePresets()):
            p = Path(tmp); c = example(); c['id'] = cases.case_id(c); cases.materialise(c, p)
            output = p / 'output.3mf'
            def write(values):
                with zipfile.ZipFile(output, 'w') as z:
                    z.writestr('Metadata/plate_1.gcode', 'G28\nG29\n')
                    z.writestr('Metadata/project_settings.config', json.dumps(values))
            good = {'printer_model': 'X1', 'layer_height': '0.2', 'wall_loops': '3', 'outer_wall_speed': ['200'],
                    'sparse_infill_density': '15%', 'filament_density': ['1.26'], 'filament_max_volumetric_speed': ['21']}
            write(good); self.assertEqual([], verify_settings.verify(output, p, c))
            write({**good, 'outer_wall_speed': ['60'], 'filament_max_volumetric_speed': ['2']})
            errors = verify_settings.verify(output, p, c)
            self.assertTrue(any('outer_wall_speed' in e for e in errors))
            self.assertTrue(any('filament_max_volumetric_speed' in e for e in errors))
            write({k: v for k, v in good.items() if k != 'wall_loops'})
            self.assertTrue(any('wall_loops' in e for e in verify_settings.verify(output, p, c)))

    def test_unknown_failure_and_bad_settings_cannot_pass_matrix(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp); ref = p / 'ref'; candidate = p / 'phone'; ref.mkdir(); candidate.mkdir()
            for d in (ref, candidate):
                (d / 'run.json').write_text(json.dumps({'sliced': False, 'cli_return_code': None, 'profile_errors': []}))
            self.assertEqual('red', matrix.classify([ref], candidate)[0])
            for d in (ref, candidate):
                (d / 'run.json').write_text(json.dumps({'sliced': True, 'cli_return_code': 0, 'profile_errors': ['bad flow']}))
            self.assertEqual('red', matrix.classify([ref], candidate)[0])

    def test_geometry_similarity_is_not_called_byte_identical(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp); ref = p / 'ref'; ref2 = p / 'ref2'; candidate = p / 'phone'; ref.mkdir(); ref2.mkdir(); candidate.mkdir()
            for d, text in ((ref, 'G28\n'), (ref2, 'G28\n'), (candidate, 'G29\n')):
                (d / 'run.json').write_text(json.dumps({'sliced': True, 'cli_return_code': 0, 'profile_errors': []}))
                with zipfile.ZipFile(d / 'out.gcode.3mf', 'w') as z:
                    z.writestr('Metadata/plate_1.gcode', text)
                    z.writestr('Metadata/project_settings.config', '{"wall_loops":"2"}')
            self.assertEqual('unverified', matrix.classify([ref], candidate)[0])
            with patch.object(matrix, 'paths', return_value={}), patch.object(matrix, 'diffs', return_value={}):
                status, detail = matrix.classify([ref, ref2], candidate)
            self.assertEqual('variant', status)
            self.assertTrue(detail['within_official_variation'])
            # A difference on layer 1 cannot excuse an unrelated error on layer 2.
            with patch.object(matrix, 'paths', return_value={}), patch.object(matrix, 'diffs', side_effect=[
                {(1, 'Outer wall'): 10.0}, {(2, 'Outer wall'): 1.0}, {(2, 'Outer wall'): 1.0},
            ]):
                self.assertEqual('red', matrix.classify([ref, ref2], candidate)[0])
            with patch.object(matrix, 'paths', return_value={}), patch.object(matrix, 'diffs', side_effect=[
                {(1, 'Outer wall'): math.inf}, {(1, 'Outer wall'): 1.0}, {(1, 'Outer wall'): 1.0},
            ]):
                self.assertEqual('unverified', matrix.classify([ref, ref2], candidate)[0])
            with zipfile.ZipFile(candidate / 'out.gcode.3mf', 'w') as z:
                z.writestr('Metadata/plate_1.gcode', 'G28\n')
                z.writestr('Metadata/project_settings.config', '{"wall_loops":"3"}')
            status, detail = matrix.classify([ref, ref2], candidate)
            self.assertEqual('red', status)
            self.assertTrue(detail.get('effective_settings_differ'))

    def test_stale_matrix_results_are_not_current(self):
        item = ('cube', 'baseline', {}); ident = {'engine_sha256': 'e', 'resources_sha256': 'r'}
        valid = {'input_format': cases.INPUT_FORMAT, 'classification_version': matrix.CLASSIFICATION_VERSION,
                 'validation_sha256': matrix.validation_hash(), 'case': 'new', 'engine': 'e', 'resources': 'r', 'reference_image': 'image',
                 'phone_model': 'test phone', 'phone_abi': 'arm64', 'phone_sdk': '28', 'phone_cpu': 0}
        with patch.object(matrix, 'cell_case', return_value={'id': 'new'}):
            self.assertTrue(matrix.current_result(valid, item, ident, 'image'))
            for changed in ({'input_format': 2}, {'validation_sha256': 'old'}, {'case': 'old'}, {'engine': 'old'}, {'resources': 'old'}, {'reference_image': 'old'}):
                self.assertFalse(matrix.current_result(valid | changed, item, ident, 'image'))

    def test_profile_cycles_and_missing_ancestors_are_rejected(self):
        lib = profiles.Presets.__new__(profiles.Presets)
        lib.by_name = {'a': {'inherits': 'b'}, 'b': {'inherits': 'a'}}
        with self.assertRaises(ValueError): lib.resolve('a')
        with self.assertRaises(ValueError): lib.includes('a')
        lib.by_name = {'a': {'inherits': 'missing'}}
        with self.assertRaises(KeyError): lib.resolve('a')

    def test_benchy_stl_integrity_and_import(self):
        data = b' ' * 80 + struct.pack('<I', 1) + struct.pack('<12fH', 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'benchy.stl'; path.write_bytes(data)
            with patch.object(models, 'BENCHY_PATH', path), patch.object(models, 'BENCHY_SHA256', hashlib.sha256(data).hexdigest()):
                mesh = models.benchy(); self.assertEqual(3, len(mesh.v)); self.assertEqual([(0, 1, 2)], mesh.t)
                path.write_bytes(data + b'x')
                with self.assertRaises(ValueError): models.benchy()

    @unittest.skipUnless(models.BENCHY_PATH.is_file(), 'requires the pinned reference resources')
    def test_benchy_model_xml_matches_editor_output(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(cases, 'preset_library', return_value=FakePresets()):
            p = Path(tmp); c = example(); c['objects'] = cases.plate('benchy'); c['id'] = cases.case_id(c)
            cases.materialise(c, p)
            with zipfile.ZipFile(p / 'model.3mf') as z:
                digest = hashlib.sha256(z.read('3D/3dmodel.model')).hexdigest()
            self.assertEqual('ad0ebfc5be3c7da9ab50176c14f3fbda1eda8fc7114dc977f3e46387072d0b98', digest)


if __name__ == '__main__':
    unittest.main()
