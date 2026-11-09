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
import geometry
from pandy_equiv import cases, models, profiles, safety, verify_settings


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
    def test_geometry_ignores_unretraction_but_keeps_full_circle_arcs(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'plate.3mf'
            with zipfile.ZipFile(p, 'w') as z:
                z.writestr('Metadata/plate_1.gcode', '\n'.join([
                    'M83', '; CHANGE_LAYER', '; FEATURE: Outer wall',
                    'G1 X10 Y10', 'G1 E.8', 'G1 X11 E.1', 'G2 I-1 J0 E.1',
                ]))
            paths = geometry.parse(p)[0]['walls']
            self.assertAlmostEqual(0.2, paths[1])
            self.assertGreater(len(paths[0]), 20)
            self.assertEqual(1, sum((pt == (10, 10)).all() for pt in paths[0]))

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
            for d, text in ((ref, 'G28\nG29\n; CHANGE_LAYER\n; Z_HEIGHT: 0.2\n'), (ref2, 'G28\nG29\n; CHANGE_LAYER\n; Z_HEIGHT: 0.2\n'), (candidate, 'G28\nG29\n; CHANGE_LAYER\n; Z_HEIGHT: 0.2\n; different\n')):
                (d / 'run.json').write_text(json.dumps({'sliced': True, 'cli_return_code': 0, 'profile_errors': []}))
                with zipfile.ZipFile(d / 'out.gcode.3mf', 'w') as z:
                    z.writestr('Metadata/plate_1.gcode', text)
                    z.writestr('Metadata/project_settings.config', '{"wall_loops":"2"}')
            self.assertEqual('unverified', matrix.classify([ref], candidate)[0])
            with patch.object(matrix, 'paths', return_value={}), patch.object(matrix, 'diffs', return_value={}):
                status, detail = matrix.classify([ref, ref2], candidate)
            self.assertEqual('variant', status)
            self.assertTrue(detail['within_official_variation'])
            # Support-only changes remain light green even when the official runs also vary.
            import numpy as np
            support = {1: {'Support': (np.array([[0., 0.], [1., 1.]]), 1.)}}
            with patch.object(matrix, 'paths', return_value=support), patch.object(matrix, 'diffs', side_effect=[
                {(1, 'Support'): .5}, {(1, 'Support'): .5}, {(1, 'Support'): .5},
            ]):
                self.assertEqual('blue', matrix.classify([ref, ref2], candidate)[0])
            # A difference on layer 1 cannot excuse an unrelated error on layer 2.
            with patch.object(matrix, 'paths', return_value={}), patch.object(matrix, 'diffs', side_effect=[
                {(1, 'Outer wall'): 10.0}, {(2, 'Outer wall'): 1.0}, {(2, 'Outer wall'): 1.0},
            ]):
                self.assertEqual('red', matrix.classify([ref, ref2], candidate)[0])
            with patch.object(matrix, 'paths', return_value={}), patch.object(matrix, 'geometry_grade', return_value='variant'), patch.object(matrix, 'diffs', side_effect=[
                {(1, 'Outer wall'): math.inf}, {(1, 'Outer wall'): 1.0}, {(1, 'Outer wall'): 1.0},
            ]):
                self.assertEqual('unverified', matrix.classify([ref, ref2], candidate)[0])
            with patch.object(matrix, 'paths', return_value={}), patch.object(matrix, 'geometry_grade', return_value='red'), patch.object(matrix, 'diffs', side_effect=[
                {(1, 'Outer wall'): math.inf}, {(1, 'Outer wall'): 1.0}, {(1, 'Outer wall'): 1.0},
            ]):
                self.assertEqual('red', matrix.classify([ref, ref2], candidate)[0])
            with zipfile.ZipFile(candidate / 'out.gcode.3mf', 'w') as z:
                z.writestr('Metadata/plate_1.gcode', 'G28\nG29\n; CHANGE_LAYER\n; Z_HEIGHT: 0.2\n')
                z.writestr('Metadata/project_settings.config', '{"wall_loops":"3"}')
            status, detail = matrix.classify([ref, ref2], candidate)
            self.assertEqual('red', status)
            self.assertTrue(detail.get('effective_settings_differ'))

    def test_tiers_separate_support_seams_infill_and_significant_changes(self):
        import numpy as np
        points = np.array([[0., 0.], [1., 1.]])
        def paths(feature, p=points, amount=1.): return {1: {feature: (p, amount)}}
        self.assertEqual('blue', matrix.geometry_grade({(1, 'Support'): 4.}, paths('Outer wall'), paths('Outer wall'), {}))
        self.assertEqual('yellow', matrix.geometry_grade({(1, 'Sparse infill'): .2}, paths('Sparse infill'), paths('Sparse infill'), {}))
        self.assertEqual('yellow', matrix.geometry_grade({(1, 'Outer wall'): .015}, paths('Outer wall'), paths('Outer wall'), {}))
        self.assertEqual('red', matrix.geometry_grade({(1, 'Inner wall'): .05}, paths('Inner wall'), paths('Inner wall'), {}))
        self.assertEqual('red', matrix.geometry_grade({(1, 'Support'): math.inf}, paths('Outer wall'), paths('Support'), {}))
        bigger = points * 1.1
        self.assertEqual('red', matrix.geometry_grade({(1, 'Outer wall'): .1}, paths('Outer wall', bigger), paths('Outer wall'), {}))
        self.assertEqual('red', matrix.geometry_grade({(1, 'Sparse infill'): .2}, paths('Sparse infill', amount=.5), paths('Sparse infill'), {}))
        self.assertEqual('red', matrix.geometry_grade({(1, 'Sparse infill'): .5}, paths('Sparse infill'), paths('Sparse infill'), {}))

    def test_candidate_safety_checks_start_and_temperatures(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'slice.3mf'
            def make(g):
                with zipfile.ZipFile(p, 'w') as z: z.writestr('Metadata/plate_1.gcode', g)
            make('G28\nG29\nM104 S220\n; CHANGE_LAYER\n'); self.assertEqual([], safety.problems(p))
            make('G28\nG29\n; CHANGE_LAYER\nM104 S999\n'); self.assertTrue(safety.problems(p))
            make('G28\nG29\n; CHANGE_LAYER\nM104S999\n'); self.assertTrue(safety.problems(p))
            make('G28\nG29\n; CHANGE_LAYER\nM190 R150\n'); self.assertTrue(safety.problems(p))
            make('G28\n; CHANGE_LAYER\nG29\n'); self.assertTrue(safety.problems(p))
            make('G28\nM1002 judge_flag auto_bed_leveling_flag\n; CHANGE_LAYER\n'); self.assertTrue(safety.problems(p))
            make('G29\nG28\n; CHANGE_LAYER\n'); self.assertTrue(safety.problems(p))
            make('G28\nG29\n'); self.assertTrue(safety.problems(p))

    def test_unsafe_identical_output_is_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp); ref = p / 'ref'; candidate = p / 'candidate'; ref.mkdir(); candidate.mkdir()
            for d in (ref, candidate):
                (d / 'run.json').write_text(json.dumps({'sliced': True, 'cli_return_code': 0, 'profile_errors': []}))
                with zipfile.ZipFile(d / 'out.gcode.3mf', 'w') as z:
                    z.writestr('Metadata/plate_1.gcode', 'G28\nG29\n; CHANGE_LAYER\nM104S999\n')
                    z.writestr('Metadata/project_settings.config', '{}')
            self.assertEqual('red', matrix.classify([ref], candidate)[0])

    def test_layer_heights_detect_dimension_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            ref, candidate = Path(tmp) / 'ref', Path(tmp) / 'candidate'
            ref.mkdir(); candidate.mkdir()
            for d, z in ((ref, '.2'), (candidate, '.3')):
                (d / 'run.json').write_text(json.dumps({'sliced': True, 'cli_return_code': 0, 'profile_errors': []}))
                with zipfile.ZipFile(d / 'out.gcode.3mf', 'w') as output:
                    output.writestr('Metadata/plate_1.gcode', f'G28\nG29\n; CHANGE_LAYER\n; Z_HEIGHT: 0{z}\n')
                    output.writestr('Metadata/project_settings.config', '{}')
            self.assertEqual('red', matrix.classify([ref, ref], candidate)[0])

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
