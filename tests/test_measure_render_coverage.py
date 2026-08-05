from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from scripts.measure_render_coverage import (
    background_reference,
    character_bounds,
    clip_mask,
    head_bounds,
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

    def test_the_pale_green_stage_is_not_mistaken_for_the_clip(self) -> None:
        # Both stage colours satisfy "green leads" and would otherwise be counted.
        region = np.array([[STAGE_TOP, STAGE_BOTTOM]], dtype=np.int16)
        self.assertEqual(clip_mask(region).tolist(), [[False, False]])


class MeasureTests(unittest.TestCase):
    def test_a_covered_head_with_decorations_reports_both(self) -> None:
        image = stage(60, 60)
        image[10:50, 10:50] = HAIR
        image[12:16, 12:16] = STAR
        image[20:22, 12:18] = CLIP
        path = write(image)
        try:
            metric = measure(path, (0, 0, 60, 60), column=3, head_fraction=1.0)
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
            metric = measure(path, (0, 0, 60, 60), column=3, head_fraction=1.0)
        finally:
            path.unlink()
        self.assertEqual(metric.hole_percent, 0.0)
        self.assertEqual(metric.star_pixels, 0)

    def test_a_stage_outside_the_image_is_rejected(self) -> None:
        path = write(stage(20, 20))
        try:
            with self.assertRaises(ValueError):
                measure(path, (0, 0, 60, 60), column=3, head_fraction=1.0)
        finally:
            path.unlink()

    def test_an_empty_stage_is_rejected(self) -> None:
        path = write(stage(60, 60))
        try:
            with self.assertRaises(ValueError):
                measure(path, (0, 0, 60, 60), column=3, head_fraction=1.0)
        finally:
            path.unlink()


class HeadBoundsTests(unittest.TestCase):
    def test_only_the_top_slice_of_the_character_is_taken(self) -> None:
        image = stage(120, 120)
        image[20:100, 30:90] = HAIR
        self.assertEqual(head_bounds(image, (0, 0, 120, 120), 0.25, column=3), (20, 30, 20, 60))


class CharacterBoundsTests(unittest.TestCase):
    def test_the_box_wraps_only_what_is_drawn(self) -> None:
        image = stage(60, 60)
        image[15:35, 20:40] = HAIR
        self.assertEqual(character_bounds(image, (0, 0, 60, 60), column=3), (15, 20, 20, 20))

    def test_an_empty_stage_has_no_character(self) -> None:
        with self.assertRaises(ValueError):
            character_bounds(stage(30, 30), (0, 0, 30, 30), column=3)


class PositionInvarianceTests(unittest.TestCase):
    """Candidates render the character at slightly different positions.

    A fixed rectangle moved decorations out of frame and reported them as lost,
    which inverted the ranking of real candidates. The measurement must depend
    on the character, not on where it happens to sit.
    """

    def draw(self, top: int, left: int) -> Path:
        image = stage(120, 120)
        image[top : top + 40, left : left + 40] = HAIR
        image[top + 2 : top + 6, left + 2 : left + 6] = STAR
        image[top + 10 : top + 12, left + 2 : left + 8] = CLIP
        image[top + 20 : top + 22, left + 20 : left + 24] = stage(120, 120)[
            top + 20 : top + 22, left + 20 : left + 24
        ]
        return write(image)

    def test_moving_the_character_does_not_change_the_metric(self) -> None:
        first, second = self.draw(10, 10), self.draw(60, 70)
        try:
            left_metric = measure(first, (0, 0, 120, 120), column=3, head_fraction=1.0)
            right_metric = measure(second, (0, 0, 120, 120), column=3, head_fraction=1.0)
        finally:
            first.unlink()
            second.unlink()
        self.assertEqual(left_metric.star_pixels, right_metric.star_pixels)
        self.assertEqual(left_metric.clip_pixels, right_metric.clip_pixels)
        self.assertEqual(left_metric.hole_pixels, right_metric.hole_pixels)
        self.assertEqual(left_metric.hole_percent, right_metric.hole_percent)
        self.assertEqual(left_metric.star_pixels, 16)
        self.assertEqual(left_metric.hole_pixels, 8)


if __name__ == "__main__":
    unittest.main()
