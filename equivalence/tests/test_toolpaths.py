import math
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pandy_equiv.toolpaths import Primitive as P, PathGeometry as G, SpatialPaths, distance, parse, ERROR_MM
from fuzzy_stats import statistics, signed_rectangle_distance


class ContinuousToolpathTests(unittest.TestCase):
    def test_line_coverage_ignores_direction_and_segmentation(self):
        a = G([P((0., 0.), (10., 0.))])
        b = G([P((10., 0.), (4., 0.)), P((4., 0.), (0., 0.))])
        self.assertEqual(0., distance(a, b))

    def test_gap_between_segments_is_detected(self):
        a = G([P((0., 0.), (1., 0.))])
        b = G([P((0., 0.), (.4, 0.)), P((.6, 0.), (1., 0.))])
        self.assertGreaterEqual(distance(a, b), .1 - 1e-10)
        self.assertLessEqual(distance(a, b), .1 + ERROR_MM + 1e-10)

    def test_full_circle_coverage_ignores_start_and_arc_splits(self):
        a = G([P((1., 0.), (1., 0.), (0., 0.), math.tau)])
        b = G([P((-1., 0.), (1., 0.), (0., 0.), -math.pi), P((1., 0.), (-1., 0.), (0., 0.), -math.pi)])
        self.assertEqual(0., distance(a, b))
        np.testing.assert_allclose(a.min(), [-1., -1.])
        np.testing.assert_allclose(a.max(), [1., 1.])

    def test_hole_radius_change_cannot_hide_behind_outer_contour(self):
        outer = P((2., 0.), (2., 0.), (0., 0.), math.tau)
        a = G([outer, P((1., 0.), (1., 0.), (0., 0.), math.tau)])
        b = G([outer, P((1.05, 0.), (1.05, 0.), (0., 0.), math.tau)])
        self.assertGreaterEqual(distance(a, b), .05 - 1e-10)
        self.assertLessEqual(distance(a, b), .05 + ERROR_MM + 1e-10)

    def test_opposite_arcs_with_shared_endpoints_are_not_equal(self):
        a = G([P((1., 0.), (-1., 0.), (0., 0.), math.pi)])
        b = G([P((1., 0.), (-1., 0.), (0., 0.), -math.pi)])
        self.assertGreater(distance(a, b), 1.)

    def test_spatial_search_checks_long_primitive_not_just_nearest_center(self):
        lines = [P((-.5, .001), (.5, .001))]
        lines += [P((i * .00001, .02), (i * .00001, .021)) for i in range(30)]
        spatial = SpatialPaths(lines)
        self.assertAlmostEqual(.001, spatial.nearest(np.array([[0., 0.]]))[0], places=10)

    def test_parallel_lines_have_certified_distance(self):
        a = G([P((0., 0.), (2., 0.))]); b = G([P((0., .017), (2., .017))])
        self.assertGreaterEqual(distance(a, b), .017)
        self.assertLessEqual(distance(a, b), .017 + ERROR_MM + 1e-10)

    def test_dense_nearest_search_and_long_constant_offset_remain_correct(self):
        circle = SpatialPaths([P((50., 0.), (50., 0.), (0., 0.), math.tau)])
        np.testing.assert_allclose(circle.nearest(np.zeros((500, 2))), 50., atol=1e-9)
        a = G([P((0., 0.), (10., 0.))]); b = G([P((0., .03), (10., .03))])
        self.assertGreaterEqual(distance(a, b), .03)
        self.assertLessEqual(distance(a, b), .03 + ERROR_MM + 1e-10)

    def test_modal_coordinates_absolute_extrusion_and_unretraction(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'plate.3mf'
            with zipfile.ZipFile(p, 'w') as z:
                z.writestr('Metadata/plate_1.gcode', '\n'.join([
                    'G90', 'M82', 'G92 E0', 'G1 X10 Y10', '; CHANGE_LAYER', '; FEATURE: Outer wall',
                    'G1 E.8', 'G1 X11 E.9', 'G91', 'G1 X1 E1.0', 'G90', 'G92 X0', 'G1 X1 E1.1',
                ]))
            geom, e = parse(p)[0]['Outer wall']
            self.assertAlmostEqual(.3, e)
            np.testing.assert_allclose(geom.min(), [10., 10.])
            np.testing.assert_allclose(geom.max(), [13., 10.])

    def test_parser_preserves_rounded_arc_endpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'plate.3mf'
            with zipfile.ZipFile(p, 'w') as z:
                z.writestr('Metadata/plate_1.gcode', 'M83\nG1 X1 Y0\n; CHANGE_LAYER\n; FEATURE: Outer wall\nG3 X0 Y1.001 I-1 J0 E.1\n')
            geom, e = parse(p)[0]['Outer wall']
            self.assertAlmostEqual(.1, e)
            self.assertAlmostEqual(1.001, geom.max()[1])

    def test_unsupported_arc_modes_fail_closed(self):
        for mode, command in [('G18', 'G2 X1 Z1 I1 K0 E.1'), ('G90.1', 'G3 X1 Y1 I1 J0 E.1'), ('G17', 'G2 X1 Y1 R1 E.1')]:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                p = Path(tmp) / 'plate.3mf'
                with zipfile.ZipFile(p, 'w') as z:
                    z.writestr('Metadata/plate_1.gcode', f'M83\n{mode}\n; CHANGE_LAYER\n; FEATURE: Outer wall\n{command}\n')
                with self.assertRaises(ValueError): parse(p)

    def test_unrecognized_motion_is_not_silently_dropped(self):
        for command in ['N10 G1 X1 Y1 E.1', 'X1 Y1 E.1', 'G5 X1 Y1 E.1']:
            with self.subTest(command=command), tempfile.TemporaryDirectory() as tmp:
                p = Path(tmp) / 'plate.3mf'
                with zipfile.ZipFile(p, 'w') as z:
                    z.writestr('Metadata/plate_1.gcode', f'M83\n; CHANGE_LAYER\n; FEATURE: Outer wall\nG1 X0 Y0\n{command}\n')
                with self.assertRaises(ValueError): parse(p)

    def test_pinned_a1_inspection_macro_requires_unchanged_xy(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'plate.3mf'
            def make(macro):
                with zipfile.ZipFile(p, 'w') as z:
                    z.writestr('Metadata/plate_1.gcode', f'M83\n; CHANGE_LAYER\n; FEATURE: Outer wall\nG0 X187 Y178\n{macro}\nG1 X188 E.1\n')
            make('G39 S1 X187 Y178')
            self.assertAlmostEqual(.1, parse(p)[0]['Outer wall'][1])
            make('G39 S1 X1 Y2')
            with self.assertRaises(ValueError): parse(p)

    def test_fuzzy_diagnostic_is_signed_and_rejects_nonrectangular_baseline(self):
        points = np.array([[.5, .5], [1.1, .5], [1.1, 1.1]])
        np.testing.assert_allclose(signed_rectangle_distance(points, np.zeros(2), np.ones(2)), [-.5, .1, math.sqrt(.02)])
        square = G([P((0., 0.), (1., 0.)), P((1., 0.), (1., 1.)), P((1., 1.), (0., 1.)), P((0., 1.), (0., 0.))])
        data = {1: {'Outer wall': (square, 1.)}}
        self.assertAlmostEqual(0., statistics(data, data)['mean_signed_mm'])
        circle = {1: {'Outer wall': (G([P((1., 0.), (1., 0.), (0., 0.), math.tau)]), 1.)}}
        with self.assertRaises(ValueError): statistics(circle, circle)


if __name__ == '__main__':
    unittest.main()
