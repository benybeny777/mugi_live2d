from __future__ import annotations

import unittest

from pipeline.fixedtopo import landmarks as lm
from pipeline.fixedtopo.palette import Palette
from tests import synthetic

PALETTE = Palette.load("pipeline/palette.mugi.json")


class LandmarkTest(unittest.TestCase):
    def test_finds_the_face_eyes_and_mouth_of_a_synthetic_character(self) -> None:
        marks, _ = lm.detect(synthetic.array(), PALETTE)
        centre = 300
        self.assertLess(marks.eye_left[0], centre)
        self.assertGreater(marks.eye_right[0], centre)
        self.assertAlmostEqual(marks.eye_left[1], marks.eye_right[1], delta=4)
        self.assertAlmostEqual(marks.mouth[0], centre, delta=12)
        self.assertGreater(marks.mouth[1], marks.eye_left[1])
        self.assertLess(marks.mouth[1], marks.chin[1])
        self.assertLess(marks.face[3], marks.subject[3])

    def test_head_is_cut_off_above_the_torso(self) -> None:
        marks, _ = lm.detect(synthetic.array(), PALETTE)
        self.assertLess(marks.head[3], marks.subject[3])
        self.assertLessEqual(marks.crown[1], marks.face[1])

    def test_measurement_is_repeatable(self) -> None:
        first, _ = lm.detect(synthetic.array(), PALETTE)
        second, _ = lm.detect(synthetic.array(), PALETTE)
        self.assertEqual(first.to_json(), second.to_json())

    def test_moving_the_eyes_moves_the_measurement(self) -> None:
        base, _ = lm.detect(synthetic.array(), PALETTE)
        shifted, _ = lm.detect(synthetic.array(eye_shift=20), PALETTE)
        self.assertAlmostEqual(shifted.eye_left[1] - base.eye_left[1], 20, delta=3)

    def test_blank_input_is_reported_not_guessed(self) -> None:
        blank = synthetic.array()
        blank[..., 3] = 0
        with self.assertRaises(lm.LandmarkError):
            lm.detect(blank, PALETTE)


if __name__ == "__main__":
    unittest.main()
