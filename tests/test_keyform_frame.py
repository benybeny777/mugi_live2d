from __future__ import annotations

import unittest

import numpy as np

from pipeline.keyform import frame as fr
from tests import keyform_fixtures as fx


class FrameTest(unittest.TestCase):
    def test_a_pure_scale_and_shift_is_recovered(self) -> None:
        source = fx.quad(0.0, 0.0, 10.0)
        target = fx.translated(fx.scaled(source, 3.0), 500.0, -200.0)
        fitted = fr.fit(source, target)
        np.testing.assert_allclose(fitted.matrix, np.eye(2) * 3.0, atol=1e-9)
        np.testing.assert_allclose(fitted.translation, (500.0, -200.0), atol=1e-9)
        self.assertAlmostEqual(fitted.scale, 3.0, places=9)
        self.assertLess(fitted.residual_rms, 1e-9)

    def test_displacement_is_scaled_but_not_translated(self) -> None:
        source = fx.quad(0.0, 0.0, 10.0)
        target = fx.translated(fx.scaled(source, 4.0), 1000.0, 1000.0)
        fitted = fr.fit(source, target)
        pushed = fitted.push(np.array([[1.0, 0.0], [0.0, -2.0]]))
        np.testing.assert_allclose(pushed, [[4.0, 0.0], [0.0, -8.0]], atol=1e-9)

    def test_rotation_is_carried_into_the_target_frame(self) -> None:
        source = fx.quad(0.0, 0.0, 10.0)
        target = fx.rotated(source, 90.0)
        fitted = fr.fit(source, target)
        pushed = fitted.push(np.array([[1.0, 0.0]]))
        np.testing.assert_allclose(pushed, [[0.0, 1.0]], atol=1e-9)

    def test_similarity_refuses_to_stretch_but_affine_accepts_it(self) -> None:
        source = fx.quad(0.0, 0.0, 10.0)
        target = [[x * 2.0, y * 0.5] for x, y in source]
        similarity = fr.fit(source, target, "similarity")
        affine = fr.fit(source, target, "affine")
        self.assertGreater(similarity.residual_rms, 1.0)
        self.assertLess(affine.residual_rms, 1e-9)
        np.testing.assert_allclose(affine.matrix, [[2.0, 0.0], [0.0, 0.5]], atol=1e-9)

    def test_a_zero_size_source_shape_has_no_frame(self) -> None:
        collapsed = [[7.0, 7.0]] * 4
        with self.assertRaises(fr.DegenerateFrameError) as caught:
            fr.fit(collapsed, fx.quad(0.0, 0.0, 10.0))
        self.assertIn("source reference shape has no extent", str(caught.exception))

    def test_a_zero_size_target_shape_has_no_frame(self) -> None:
        with self.assertRaises(fr.DegenerateFrameError) as caught:
            fr.fit(fx.quad(0.0, 0.0, 10.0), [[3.0, 4.0]] * 4)
        self.assertIn("target reference shape has no extent", str(caught.exception))

    def test_a_collinear_reference_shape_is_refused_in_either_mode(self) -> None:
        line = [[0.0, 0.0], [1.0, 1.0], [2.0, 2.0], [3.0, 3.0]]
        for mode in fr.MODES:
            with self.subTest(mode=mode):
                with self.assertRaises(fr.DegenerateFrameError) as caught:
                    fr.fit(line, fx.quad(0.0, 0.0, 10.0), mode)
                self.assertIn("source reference shape is collinear", str(caught.exception))
                with self.assertRaises(fr.DegenerateFrameError) as caught:
                    fr.fit(fx.quad(0.0, 0.0, 10.0), line, mode)
                self.assertIn("target reference shape is collinear", str(caught.exception))

    def test_shapes_of_different_length_are_refused(self) -> None:
        with self.assertRaises(ValueError):
            fr.fit(fx.quad(0.0, 0.0, 1.0), [[0.0, 0.0], [1.0, 1.0]])

    def test_an_unknown_mode_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            fr.fit(fx.quad(0.0, 0.0, 1.0), fx.quad(0.0, 0.0, 2.0), "elastic")

    def test_non_finite_reference_shapes_are_refused(self) -> None:
        broken = fx.quad(0.0, 0.0, 10.0)
        broken[1][0] = float("nan")
        with self.assertRaises(fr.DegenerateFrameError):
            fr.fit(broken, fx.quad(0.0, 0.0, 10.0))

    def test_extent_is_the_rms_radius(self) -> None:
        points = np.array(fx.quad(1000.0, -50.0, 10.0))
        self.assertAlmostEqual(fr.extent(points), float(np.hypot(10.0, 10.0)), places=9)

    def test_the_frame_serialises_to_plain_numbers(self) -> None:
        fitted = fr.fit(fx.quad(0.0, 0.0, 10.0), fx.quad(5.0, 5.0, 20.0))
        document = fitted.to_json()
        self.assertEqual(document["mode"], "similarity")
        self.assertEqual(len(document["linear"]), 2)
        self.assertAlmostEqual(float(document["scale"]), 2.0, places=9)


if __name__ == "__main__":
    unittest.main()
