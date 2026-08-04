from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np

from pipeline.sandbox import export
from pipeline.sandbox import manifest as mf
from tests import sandbox_fixtures as fixtures


class RegionTest(unittest.TestCase):
    def test_editable_is_a_ring_outside_the_artwork(self) -> None:
        base = fixtures.disc()
        present, locked, editable = export.regions(base, grow=10.0, seam=2.0, target=None)
        self.assertFalse((editable & present).any())
        self.assertFalse((editable & locked).any())
        self.assertTrue(editable.any())
        self.assertEqual(int((editable | present).sum()), int(np.count_nonzero(editable | present)))

    def test_the_seam_ring_keeps_the_alpha_edge_unlocked(self) -> None:
        base = fixtures.disc()
        _, tight, _ = export.regions(base, grow=4.0, seam=0.0, target=None)
        _, relaxed, _ = export.regions(base, grow=4.0, seam=3.0, target=None)
        self.assertLess(int(relaxed.sum()), int(tight.sum()))

    def test_a_target_box_adds_an_editable_area_away_from_the_artwork(self) -> None:
        base = fixtures.disc()
        _, _, editable = export.regions(base, grow=0.0, seam=2.0, target=(0, 0, 12, 12))
        self.assertTrue(editable[5, 5])

    def test_the_crop_covers_the_work_plus_the_margin(self) -> None:
        base = fixtures.disc()
        present, _, editable = export.regions(base, grow=10.0, seam=2.0, target=None)
        box = export.sandbox_box(present, editable, margin=5, canvas=fixtures.CANVAS)
        x0, y0, x1, y1 = box
        self.assertEqual((x0, y0, x1, y1), (45, 45, 156, 156))

    def test_the_crop_is_clipped_to_the_canvas(self) -> None:
        base = fixtures.disc(radius=95)
        present, _, editable = export.regions(base, grow=20.0, seam=2.0, target=None)
        self.assertEqual(
            export.sandbox_box(present, editable, margin=40, canvas=fixtures.CANVAS),
            (0, 0, 200, 200),
        )


class WriteSandboxTest(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = Path(tempfile.mkdtemp(prefix="sandbox-export-"))
        self.addCleanup(shutil.rmtree, self.directory, ignore_errors=True)
        self.base = fixtures.disc()

    def _write(self, out: Path) -> mf.Manifest:
        return export.write_sandbox(self.base, fixtures.source(), out, "face", grow=10.0)

    def test_it_writes_the_three_inputs_and_a_manifest(self) -> None:
        document = self._write(self.directory)
        sandbox = self.directory / "face"
        for name in ("base.png", "editable.png", "locked.png", "manifest.json"):
            self.assertTrue((sandbox / name).exists(), name)
        self.assertEqual(document.canvas, (200, 200))
        self.assertEqual(document.size, tuple(document.sandbox["size"]))

    def test_the_written_files_match_their_recorded_hashes(self) -> None:
        document = self._write(self.directory)
        self.assertEqual(mf.verify_files(document, self.directory / "face"), [])

    def test_an_edited_input_is_detected(self) -> None:
        document = self._write(self.directory)
        sandbox = self.directory / "face"
        fixtures.save(fixtures.disc(radius=20), sandbox / "base.png")
        problems = mf.verify_files(document, sandbox)
        self.assertTrue(any("base.png" in problem for problem in problems))

    def test_two_runs_produce_identical_files(self) -> None:
        first = self._write(self.directory / "a")
        second = self._write(self.directory / "b")
        self.assertEqual(first.raw, second.raw)
        for role in ("base", "editable", "locked"):
            self.assertEqual(first.files[role].sha256, second.files[role].sha256)

    def test_the_manifest_survives_a_round_trip(self) -> None:
        written = self._write(self.directory)
        reloaded = mf.load(self.directory / "face" / "manifest.json")
        self.assertEqual(reloaded.raw, written.raw)
        self.assertEqual(reloaded.box, written.box)
        self.assertIn("Never run generative fill on the master PSD", " ".join(reloaded.rules))

    def test_the_paste_origin_is_the_top_left_of_the_crop(self) -> None:
        document = self._write(self.directory)
        self.assertEqual(document.ret["paste_origin"], list(document.box[:2]))

    def test_the_crop_masks_agree_with_the_recorded_counts(self) -> None:
        document = self._write(self.directory)
        sandbox = self.directory / "face"
        editable = fixtures.load_mask(sandbox / "editable.png")
        locked = fixtures.load_mask(sandbox / "locked.png")
        self.assertEqual(int(editable.sum()), document.sandbox["editable_pixels"])
        self.assertEqual(int(locked.sum()), document.sandbox["locked_pixels"])
        self.assertEqual(editable.shape, (document.size[1], document.size[0]))

    def test_an_unknown_schema_is_rejected(self) -> None:
        path = self.directory / "face" / "manifest.json"
        self._write(self.directory)
        path.write_text('{"schema": "other@9", "id": "x"}', encoding="utf-8")
        with self.assertRaises(ValueError):
            mf.load(path)

    def test_nothing_to_generate_is_an_error(self) -> None:
        with self.assertRaises(ValueError):
            export.write_sandbox(self.base, fixtures.source(), self.directory, "none", grow=0.0)


if __name__ == "__main__":
    unittest.main()
