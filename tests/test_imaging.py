from __future__ import annotations

import unittest

import numpy as np

from pipeline.fixedtopo import imaging


class ImagingTest(unittest.TestCase):
    def test_dilate_and_erode_are_exact_radii(self) -> None:
        mask = np.zeros((41, 41), dtype=bool)
        mask[20, 20] = True
        grown = imaging.dilate(mask, 5.0)
        self.assertTrue(grown[20, 15])
        self.assertFalse(grown[20, 14])
        self.assertEqual(imaging.bbox(grown), (15, 15, 26, 26))
        self.assertFalse(imaging.erode(grown, 5.0)[20, 15])

    def test_close_bridges_a_gap_without_moving_the_outer_edge(self) -> None:
        mask = np.zeros((21, 40), dtype=bool)
        mask[8:13, 4:14] = True
        mask[8:13, 22:32] = True
        closed = imaging.close(mask, 6.0)
        self.assertTrue(closed[10, 18])
        self.assertEqual(imaging.bbox(closed), (4, 8, 32, 13))

    def test_four_connectivity_keeps_diagonal_touches_apart(self) -> None:
        mask = np.zeros((10, 10), dtype=bool)
        mask[2, 2] = True
        mask[3, 3] = True
        _, sizes = imaging.label(mask)
        self.assertEqual(sizes.tolist(), [1, 1])

    def test_remove_small_drops_only_the_small_components(self) -> None:
        mask = np.zeros((20, 20), dtype=bool)
        mask[2:8, 2:8] = True
        mask[15, 15] = True
        cleaned = imaging.remove_small(mask, 10)
        self.assertTrue(cleaned[4, 4])
        self.assertFalse(cleaned[15, 15])

    def test_ellipse_mask_stays_inscribed_in_its_box(self) -> None:
        box = (10, 10, 50, 40)
        mask = imaging.ellipse_mask((60, 80), box)
        x0, y0, x1, y1 = imaging.bbox(mask)
        self.assertGreaterEqual(x0, box[0])
        self.assertGreaterEqual(y0, box[1])
        self.assertLessEqual(x1, box[2])
        self.assertLessEqual(y1, box[3])
        self.assertGreater(x1 - x0, 0.9 * (box[2] - box[0]))
        self.assertFalse(mask[10, 10])
        self.assertTrue(mask[25, 30])

    def test_hsv_matches_known_colours(self) -> None:
        rgb = np.array([[[255, 0, 0], [0, 255, 0], [128, 128, 128]]], dtype=np.uint8)
        hue, saturation, value = imaging.hsv(rgb)
        self.assertAlmostEqual(float(hue[0, 0]), 0.0, places=3)
        self.assertAlmostEqual(float(hue[0, 1]), 120.0, places=3)
        self.assertAlmostEqual(float(saturation[0, 2]), 0.0, places=3)
        self.assertAlmostEqual(float(value[0, 2]), 128 / 255, places=3)


if __name__ == "__main__":
    unittest.main()
