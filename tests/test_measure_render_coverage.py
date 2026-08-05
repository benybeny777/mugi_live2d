from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from scripts.measure_render_coverage import (
    background_reference,
    clip_mask,
    hole_mask,
    measure,
    star_mask,
)

STAGE_TOP = (238, 245, 235)
STAGE_BOTTOM = (202, 218, 200)
HAIR = (175, 150, 129)
STAR = (250, 190, 60)
CLIP = (90, 150, 95)


def stage(height: int, width: int) -> np.ndarray:
    """A vertical gradient like the viewer stage, with no character drawn."""
    image = np.zeros((height, width, 3), dtype=np.uint8)
    for row in range(height):
        blend = row / max(height - 1, 1)
        image[row, :] = [
            round(STAGE_TOP[channel] * (1 - blend) + STAGE_BOTTOM[channel] * blend)
            for channel in range(3)
        ]
    return image


def write(image: np.ndarray) -> Path:
    handle = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    handle.close()
    Image.fromarray(image, "RGB").save(handle.name)
    return Path(handle.name)


class BackgroundReferenceTests(unittest.TestCase):
    def test_the_reference_follows_the_gradient_per_row(self) -> None:
        reference = background_reference(stage(40, 30), column=3)
        self.assertEqual(tuple(reference[0]), STAGE_TOP)
        self.assertEqual(tuple(reference[-1]), STAGE_BOTTOM)

    def test_a_column_outside_the_image_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            background_reference(stage(10, 5), column=99)


class HoleMaskTests(unittest.TestCase):
    def test_an_empty_stage_is_all_holes(self) -> None:
        self.assertTrue(hole_mask(stage(40, 40), (5, 10, 20, 20), column=3).all())

    def test_hair_covering_the_roi_leaves_no_holes(self) -> None:
        image = stage(40, 40)
        image[5:25, 10:30] = HAIR
        self.assertFalse(hole_mask(image, (5, 10, 20, 20), column=3).any())

    def test_a_gap_in_the_hair_is_counted(self) -> None:
        image = stage(40, 40)
        image[5:25, 10:30] = HAIR
        image[10:12, 15:18] = stage(40, 40)[10:12, 15:18]
        self.assertEqual(hole_mask(image, (5, 10, 20, 20), column=3).sum(), 6)

    def test_hair_close_to_the_background_colour_is_not_a_hole(self) -> None:
        image = stage(40, 40)
        # A pale highlight 20 levels from the stage must not read as a hole.
        image[5:25, 10:30] = np.asarray(stage(40, 40)[5:25, 10:30], dtype=int) - 20
        self.assertFalse(hole_mask(image, (5, 10, 20, 20), column=3).any())


class DecorationMaskTests(unittest.TestCase):
    def test_the_star_is_detected_and_hair_is_not(self) -> None:
        region = np.array([[STAR, HAIR, STAGE_TOP]], dtype=np.int16)
        self.assertEqual(star_mask(region).tolist(), [[True, False, False]])

    def test_the_clip_is_detected_and_hair_is_not(self) -> None:
        region = np.array([[CLIP, HAIR, STAR]], dtype=np.int16)
        self.assertEqual(clip_mask(region).tolist(), [[True, False, False]])


class MeasureTests(unittest.TestCase):
    def test_a_covered_head_with_decorations_reports_both(self) -> None:
        image = stage(60, 60)
        image[10:50, 10:50] = HAIR
        image[12:16, 12:16] = STAR
        image[20:22, 12:18] = CLIP
        path = write(image)
        try:
            metric = measure(path, (10, 10, 40, 40), column=3)
        finally:
            path.unlink()
        self.assertEqual(metric.hole_pixels, 0)
        self.assertEqual(metric.star_pixels, 16)
        self.assertEqual(metric.clip_pixels, 12)
        self.assertEqual(metric.roi_pixels, 1600)

    def test_a_fill_that_erases_decorations_is_visible_in_the_metric(self) -> None:
        image = stage(60, 60)
        image[10:50, 10:50] = HAIR
        path = write(image)
        try:
            metric = measure(path, (10, 10, 40, 40), column=3)
        finally:
            path.unlink()
        self.assertEqual(metric.hole_percent, 0.0)
        self.assertEqual(metric.star_pixels, 0)

    def test_an_roi_outside_the_image_is_rejected(self) -> None:
        path = write(stage(20, 20))
        try:
            with self.assertRaises(ValueError):
                measure(path, (10, 10, 40, 40), column=3)
        finally:
            path.unlink()


if __name__ == "__main__":
    unittest.main()
