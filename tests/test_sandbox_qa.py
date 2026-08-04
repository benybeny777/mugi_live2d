from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np

from pipeline.fixedtopo import imaging
from pipeline.sandbox import export, qa, restore
from pipeline.sandbox import manifest as mf
from tests import sandbox_fixtures as fixtures


class SandboxCase(unittest.TestCase):
    """A sandbox exported from a synthetic disc, ready for a returned image."""

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="sandbox-qa-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.layer = fixtures.disc()
        self.manifest = export.write_sandbox(
            self.layer, fixtures.source(), self.root, "face", grow=12.0, margin=8
        )
        self.directory = self.root / "face"
        x0, y0, x1, y1 = self.manifest.box
        self.base = self.layer[y0:y1, x0:x1]
        self.editable = fixtures.load_mask(self.directory / "editable.png")
        self.locked = fixtures.load_mask(self.directory / "locked.png")

    def report(self, filled: np.ndarray) -> dict:
        """Write a returned image and run every check over it."""
        path = self.directory / "filled.png"
        fixtures.save(filled, path)
        return qa.evaluate(self.manifest, self.directory, path)

    def assertFails(self, report: dict, check: str) -> None:
        """Assert the report was rejected by one named check."""
        self.assertEqual(report["status"], "rejected", report["failed"])
        self.assertIn(check, report["failed"])


class GoodFillTest(SandboxCase):
    def test_a_flat_matching_fill_passes_every_check(self) -> None:
        report = self.report(fixtures.fill(self.base, self.editable))
        self.assertEqual(report["failed"], [])

    def test_passing_every_check_still_does_not_accept_the_image(self) -> None:
        report = self.report(fixtures.fill(self.base, self.editable))
        self.assertEqual(report["status"], "review_required")
        self.assertNotIn("approved", report["status"])


class FabricRegressionTest(SandboxCase):
    """The failure this pipeline exists for: a woven cloth texture in the fill.

    Photoshop's generative fill returned fabric where flat skin was asked for.
    A colour check alone lets that through, so these assertions pin the texture
    and pattern measures that catch it.
    """

    def test_a_woven_fill_is_rejected(self) -> None:
        report = self.report(fixtures.fabric(self.base, self.editable))
        self.assertEqual(report["status"], "rejected")
        self.assertIn("texture_flatness", report["failed"])
        self.assertIn("pattern_free", report["failed"])

    def test_a_weave_faint_enough_to_pass_a_colour_check_is_still_rejected(self) -> None:
        report = self.report(fixtures.fabric(self.base, self.editable, amplitude=8.0))
        colour = next(check for check in report["checks"] if check["name"] == "colour_match")
        self.assertTrue(colour["ok"], colour)
        self.assertEqual(report["status"], "rejected")

    def test_a_faint_weave_is_still_rejected(self) -> None:
        report = self.report(fixtures.fabric(self.base, self.editable, amplitude=5.0))
        self.assertEqual(report["status"], "rejected")

    def test_texture_energy_separates_flat_from_woven(self) -> None:
        interior = imaging.erode(self.editable, qa.INTERIOR_EROSION)
        flat = qa.texture_energy(fixtures.fill(self.base, self.editable), interior)
        woven = qa.texture_energy(fixtures.fabric(self.base, self.editable), interior)
        self.assertLess(flat, 1.0)
        self.assertGreater(woven, 10 * max(flat, 0.01))

    def test_the_periodicity_measure_finds_the_weave(self) -> None:
        interior = imaging.erode(self.editable, qa.INTERIOR_EROSION)
        flat, _ = qa.periodicity(fixtures.fill(self.base, self.editable), interior)
        woven, _ = qa.periodicity(
            fixtures.fabric(self.base, self.editable, period=6), interior
        )
        self.assertEqual(flat, 0.0)
        self.assertGreater(woven, mf.DEFAULT_TOLERANCES["pattern_periodicity"])


class ShadedArtworkTest(unittest.TestCase):
    """A layer that is dark along one edge and light along another.

    The colour check compares each filled pixel with the artwork it borders.
    Averaging a band of artwork instead would call a correct extension of
    Mugi's hair-toned face edge a 200-unit colour error.
    """

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="sandbox-shaded-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        layer = fixtures.shaded_disc()
        self.manifest = export.write_sandbox(
            layer, fixtures.source(), self.root, "face", grow=12.0, margin=8
        )
        self.directory = self.root / "face"
        x0, y0, x1, y1 = self.manifest.box
        self.base = layer[y0:y1, x0:x1]
        self.editable = fixtures.load_mask(self.directory / "editable.png")

    def _report(self, filled: np.ndarray) -> dict:
        path = self.directory / "filled.png"
        fixtures.save(filled, path)
        return qa.evaluate(self.manifest, self.directory, path)

    def test_extending_each_edge_with_its_own_colour_passes(self) -> None:
        report = self._report(fixtures.extend(self.base, self.editable))
        self.assertEqual(report["failed"], [])

    def test_one_flat_colour_over_both_tones_is_rejected(self) -> None:
        report = self._report(fixtures.fill(self.base, self.editable, fixtures.SKIN))
        self.assertIn("colour_match", report["failed"])

    def test_a_weave_over_shaded_artwork_is_still_caught(self) -> None:
        report = self._report(fixtures.fabric(self.base, self.editable))
        self.assertIn("pattern_free", report["failed"])


class UnderlayTest(unittest.TestCase):
    """The 2026-08-04 face return: a flat ellipse painted under the artwork.

    Every edge of Mugi's face layer is a drawn, hair-toned rim, so an underlay
    that correctly continues the skin borders a colour it must not copy. The
    numbers from that run are the ones pinned here: the returned fill was the
    artwork's own [250, 235, 215] and the old check still measured a median
    distance of 74 against the rim it happened to touch.
    """

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="sandbox-underlay-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.layer = fixtures.capped_oval()
        self.region = fixtures.oval_region()
        self.manifest = export.write_sandbox(
            self.layer,
            fixtures.source(),
            self.root,
            "face",
            grow=8.0,
            margin=8,
            region=self.region,
        )
        self.directory = self.root / "face"
        x0, y0, x1, y1 = self.manifest.box
        self.base = self.layer[y0:y1, x0:x1]
        self.oval = self.region.shifted(-x0, -y0).box

    def _report(self, filled: np.ndarray) -> dict:
        path = self.directory / "filled.png"
        fixtures.save(filled, path)
        return qa.evaluate(self.manifest, self.directory, path)

    def _colour(self, report: dict) -> dict:
        return next(check for check in report["checks"] if check["name"] == "colour_match")

    def test_the_sandbox_declares_the_shape_and_the_colour_to_use(self) -> None:
        sandbox = self.manifest.sandbox
        self.assertEqual(sandbox["fill_mode"], export.UNDERLAY)
        self.assertEqual(sandbox["region"]["box"], list(self.oval))
        self.assertEqual(tuple(sandbox["base_colour"]), fixtures.SKIN)
        self.assertIn("below", " ".join(self.manifest.rules))

    def test_a_base_colour_underlay_is_not_rejected_for_bordering_the_drawn_rim(self) -> None:
        report = self._report(fixtures.underlay(self.base, self.oval))
        self.assertEqual(report["failed"], [])
        detail = self._colour(report)["detail"]
        self.assertEqual(detail["mode"], export.UNDERLAY)
        self.assertEqual(tuple(detail["art_rgb"]), fixtures.SKIN)
        self.assertLess(detail["distance_median"], 1.0)

    def test_it_still_stops_at_review_required(self) -> None:
        report = self._report(fixtures.underlay(self.base, self.oval))
        self.assertEqual(report["status"], "review_required")
        self.assertNotEqual(report["status"], "approved")

    def test_an_underlay_larger_than_the_shape_is_rejected(self) -> None:
        """What the real return did: the ellipse was drawn past the contract oval."""
        report = self._report(fixtures.underlay(self.base, self.oval, grow=6))
        self.assertEqual(report["status"], "rejected")
        self.assertIn("silhouette", report["failed"])
        self.assertTrue(self._colour(report)["ok"], "the colour was never the problem")

    def test_a_stone_coloured_underlay_is_still_rejected(self) -> None:
        report = self._report(fixtures.underlay(self.base, self.oval, colour=fixtures.STONE))
        self.assertEqual(report["status"], "rejected")
        self.assertIn("colour_match", report["failed"])

    def test_a_woven_underlay_is_still_rejected(self) -> None:
        painted = fixtures.underlay_mask(self.base, self.oval)
        report = self._report(fixtures.fabric(self.base, painted, colour=fixtures.SKIN))
        self.assertEqual(report["status"], "rejected")
        self.assertIn("texture_flatness", report["failed"])
        self.assertIn("pattern_free", report["failed"])

    def test_an_edge_extension_reading_of_the_same_image_is_what_used_to_reject_it(self) -> None:
        """The old contract, run over the good underlay, to show what changed."""
        raw = dict(self.manifest.raw)
        raw["sandbox"] = dict(raw["sandbox"], fill_mode=export.EXTEND)
        as_extend = mf.Manifest(
            raw["id"],
            raw["source"],
            raw["sandbox"],
            self.manifest.files,
            raw["return"],
            self.manifest.tolerances,
            self.manifest.rules,
            raw,
        )
        path = self.directory / "filled.png"
        fixtures.save(fixtures.underlay(self.base, self.oval), path)
        report = qa.evaluate(as_extend, self.directory, path)
        self.assertIn("colour_match", report["failed"])


class RejectionTest(SandboxCase):
    def test_a_resized_return_is_rejected(self) -> None:
        good = fixtures.fill(self.base, self.editable)
        self.assertFails(self.report(good[:-4, :-4]), "return_size")

    def test_repainting_locked_artwork_is_rejected(self) -> None:
        filled = fixtures.fill(self.base, self.editable)
        filled[..., :3] = np.where(self.locked[..., None], np.uint8(0), filled[..., :3])
        self.assertFails(self.report(filled), "locked_untouched")

    def test_paint_outside_the_editable_region_is_rejected(self) -> None:
        filled = fixtures.fill(self.base, self.editable)
        filled[0:3, 0:3] = np.array([10, 20, 30, 255], dtype=np.uint8)
        self.assertFails(self.report(filled), "silhouette")

    def test_erasing_existing_artwork_is_rejected(self) -> None:
        filled = fixtures.fill(self.base, self.editable)
        filled[..., 3] = np.where(self.locked, np.uint8(0), filled[..., 3])
        self.assertFails(self.report(filled), "silhouette")

    def test_a_wrongly_coloured_fill_is_rejected(self) -> None:
        filled = fixtures.fill(self.base, self.editable, colour=(60, 90, 200))
        self.assertFails(self.report(filled), "colour_match")

    def test_a_half_transparent_fill_is_rejected(self) -> None:
        filled = fixtures.fill(self.base, self.editable)
        filled[..., 3] = np.where(self.editable, np.uint8(120), filled[..., 3])
        self.assertFails(self.report(filled), "alpha_solid")

    def test_an_edited_sandbox_input_is_rejected(self) -> None:
        filled = fixtures.fill(self.base, self.editable)
        fixtures.save(np.zeros_like(self.base), self.directory / "editable.png")
        self.assertFails(self.report(filled), "inputs_intact")


class RestoreTest(SandboxCase):
    def setUp(self) -> None:
        super().setUp()
        self.psd = self.root / "layer.png"
        fixtures.save(self.layer, self.psd)
        raw = json.loads((self.directory / "manifest.json").read_text(encoding="utf-8"))
        raw["source"]["psd"] = str(self.psd)
        raw["source"]["psd_sha256"] = mf.sha256_file(self.psd)
        (self.directory / "manifest.json").write_text(
            json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        self.out = self.root / "completed.png"

    def _restore(self, filled: np.ndarray, reviewed_by: str | None) -> dict:
        path = self.directory / "filled.png"
        fixtures.save(filled, path)
        return restore.restore(self.directory, path, self.out, reviewed_by, self.psd)

    def test_a_good_fill_is_not_written_without_a_reviewer(self) -> None:
        report = self._restore(fixtures.fill(self.base, self.editable), None)
        self.assertEqual(report["status"], "review_required")
        self.assertIsNone(report["written"])
        self.assertFalse(self.out.exists())

    def test_a_reviewed_fill_is_written_back_at_the_paste_origin(self) -> None:
        filled = fixtures.fill(self.base, self.editable)
        report = self._restore(filled, "codex")
        self.assertEqual(report["status"], "approved")
        self.assertTrue(self.out.exists())
        written = fixtures.load_rgba(self.out)
        self.assertEqual(written.shape, self.layer.shape)
        x0, y0, x1, y1 = self.manifest.box
        np.testing.assert_array_equal(written[y0:y1, x0:x1], filled)

    def test_a_rejected_fill_is_never_written_even_when_reviewed(self) -> None:
        report = self._restore(fixtures.fabric(self.base, self.editable), "codex")
        self.assertEqual(report["status"], "rejected")
        self.assertFalse(self.out.exists())

    def test_a_changed_source_document_stops_the_import(self) -> None:
        fixtures.save(fixtures.disc(radius=30), self.psd)
        with self.assertRaises(ValueError):
            self._restore(fixtures.fill(self.base, self.editable), "codex")


if __name__ == "__main__":
    unittest.main()
