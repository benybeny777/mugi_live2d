from __future__ import annotations

import unittest

import numpy as np

from pipeline.sandbox import psdlayer
from tests.sandbox_fixtures import FakeGroup, FakeLayer


def _colour(shape, value=(1.0, 0.5, 0.25)):
    return np.tile(np.array(value, dtype=np.float32), (*shape, 1))


class ExtractTest(unittest.TestCase):
    def test_layer_mask_is_baked_into_alpha(self) -> None:
        mask = np.zeros((10, 10, 1), dtype=np.float32)
        mask[2:6, 3:8] = 1.0
        layer = FakeLayer("顔", _colour((10, 10)), mask=mask)
        rgba = psdlayer.extract(layer, (10, 10))
        self.assertEqual(rgba.shape, (10, 10, 4))
        self.assertEqual(int(rgba[4, 4, 3]), 255)
        self.assertEqual(int(rgba[0, 0, 3]), 0)
        self.assertEqual(rgba[4, 4, :3].tolist(), [255, 128, 64])

    def test_layer_opacity_is_ignored_unless_asked_for(self) -> None:
        mask = np.ones((4, 4, 1), dtype=np.float32)
        layer = FakeLayer("口中", _colour((4, 4)), mask=mask, opacity=0)
        self.assertEqual(int(psdlayer.extract(layer, (4, 4))[0, 0, 3]), 255)
        self.assertEqual(int(psdlayer.extract(layer, (4, 4), apply_opacity=True)[0, 0, 3]), 0)

    def test_transparency_and_mask_are_multiplied(self) -> None:
        shape = np.full((4, 4, 1), 0.5, dtype=np.float32)
        mask = np.full((4, 4, 1), 0.5, dtype=np.float32)
        layer = FakeLayer("後ろ髪", _colour((4, 4)), shape=shape, mask=mask)
        self.assertEqual(int(psdlayer.extract(layer, (4, 4))[0, 0, 3]), 64)

    def test_a_smaller_layer_is_placed_at_its_offset(self) -> None:
        solid = np.ones((4, 4, 1), np.float32)
        layer = FakeLayer("前髪", _colour((4, 4)), mask=solid, offset=(6, 2))
        rgba = psdlayer.extract(layer, (12, 12))
        self.assertEqual(int(rgba[3, 7, 3]), 255)
        self.assertEqual(int(rgba[0, 0, 3]), 0)

    def test_a_layer_hanging_off_the_canvas_is_cropped(self) -> None:
        solid = np.ones((4, 4, 1), np.float32)
        layer = FakeLayer("装飾", _colour((4, 4)), mask=solid, offset=(-2, 6))
        rgba = psdlayer.extract(layer, (8, 8))
        self.assertEqual(int(rgba[6, 0, 3]), 255)
        self.assertEqual(int(rgba[..., 3].sum()), 255 * 4)

    def test_a_layer_with_no_colour_is_empty(self) -> None:
        self.assertFalse(psdlayer.extract(FakeLayer("空", None), (5, 5)).any())


class ResolveTest(unittest.TestCase):
    def setUp(self) -> None:
        self.document = FakeGroup(
            "root",
            [
                FakeGroup("顔", [FakeLayer("顔", None), FakeLayer("鼻", None)]),
                FakeGroup("髪（後ろ）", [FakeLayer("後ろ髪", None)]),
            ],
        )

    def test_walk_reports_full_paths(self) -> None:
        self.assertEqual(
            [path for path, _ in psdlayer.walk(self.document)],
            ["/顔/顔", "/顔/鼻", "/髪（後ろ）/後ろ髪"],
        )

    def test_a_unique_leaf_name_resolves(self) -> None:
        self.assertEqual(psdlayer.resolve(self.document, "後ろ髪").name, "後ろ髪")

    def test_a_full_path_wins_over_an_ambiguous_leaf(self) -> None:
        self.assertEqual(psdlayer.resolve(self.document, "/顔/顔").name, "顔")

    def test_an_unknown_name_is_reported(self) -> None:
        with self.assertRaises(KeyError):
            psdlayer.resolve(self.document, "存在しない")

    def test_describe_lists_every_pixel_layer(self) -> None:
        entries = psdlayer.describe(self.document)
        self.assertEqual(len(entries), 3)
        self.assertEqual(entries[0]["path"], "/顔/顔")


if __name__ == "__main__":
    unittest.main()
