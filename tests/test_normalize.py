from __future__ import annotations

import unittest

import numpy as np

from pipeline.fixedtopo import normalize


class NormalizeTest(unittest.TestCase):
    def test_fit_recovers_a_known_similarity(self) -> None:
        source = [(10.0, 10.0), (110.0, 10.0), (60.0, 90.0)]
        target = [(120.0, 40.0), (320.0, 40.0), (220.0, 200.0)]
        transform = normalize.fit(source, target, allow_rotation=False)
        self.assertAlmostEqual(transform.scale, 2.0, places=6)
        for mapped, wanted in zip(transform.apply(source), target):
            self.assertAlmostEqual(mapped[0], wanted[0], places=4)
            self.assertAlmostEqual(mapped[1], wanted[1], places=4)

    def test_rotation_is_only_used_when_allowed(self) -> None:
        source = [(0.0, 0.0), (100.0, 0.0)]
        target = [(0.0, 0.0), (0.0, 100.0)]
        free = normalize.fit(source, target, allow_rotation=True)
        locked = normalize.fit(source, target, allow_rotation=False)
        self.assertAlmostEqual(abs(free.rotation), np.pi / 2, places=6)
        self.assertEqual(locked.rotation, 0.0)

    def test_degenerate_landmarks_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            normalize.fit([(5.0, 5.0), (5.0, 5.0)], [(1.0, 1.0), (2.0, 2.0)])

    def test_resample_places_the_subject_where_the_transform_says(self) -> None:
        source = np.zeros((40, 40, 4), dtype=np.uint8)
        source[10:20, 10:20] = (255, 0, 0, 255)
        transform = normalize.Similarity(scale=2.0, rotation=0.0, translation=(10.0, 20.0))
        out = normalize.resample(source, transform, (100, 100), "nearest")
        rows, columns = np.nonzero(out[..., 3] > 0)
        self.assertEqual((int(columns.min()), int(rows.min())), (30, 40))
        self.assertEqual((int(columns.max()), int(rows.max())), (49, 59))

    def test_resample_does_not_drag_background_into_the_outline(self) -> None:
        source = np.zeros((40, 40, 4), dtype=np.uint8)
        source[10:30, 10:30] = (255, 255, 255, 255)
        transform = normalize.Similarity(scale=1.5, rotation=0.0, translation=(0.0, 0.0))
        out = normalize.resample(source, transform, (80, 80), "bicubic")
        edge = out[..., :3][out[..., 3] > 32]
        self.assertGreaterEqual(int(edge.min()), 200)


if __name__ == "__main__":
    unittest.main()
