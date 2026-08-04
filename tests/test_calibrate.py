from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pipeline.fixedtopo import calibrate, contract
from pipeline.fixedtopo import landmarks as lm
from pipeline.fixedtopo.palette import Palette
from tests import synthetic

SPEC = json.loads(Path("pipeline/contract-spec.mugi-hiyori-v2.json").read_text(encoding="utf-8"))
PALETTE = Palette.load("pipeline/palette.mugi.json")


def _build(spec: dict | None = None) -> dict:
    marks, _ = lm.detect(synthetic.array(), PALETTE)
    return calibrate.build(spec or SPEC, marks, {"reference": "synthetic"})


class CalibrateTest(unittest.TestCase):
    def test_calibrated_face_meets_the_spec_minimum(self) -> None:
        document = _build()
        box = document["regions"]["Face"]["box"]
        minimum = SPEC["minimum_bbox"]["Face"]
        self.assertGreaterEqual(box[2] - box[0], minimum["width"])
        self.assertGreaterEqual(box[3] - box[1], minimum["height"])

    def test_head_is_centred_and_hung_from_the_crown_margin(self) -> None:
        document = _build()
        head = document["frame"]["head"]
        self.assertAlmostEqual((head[0] + head[2]) / 2, SPEC["canvas"]["width"] / 2, delta=2)
        self.assertAlmostEqual(head[1], SPEC["proportions"]["crown_margin"], delta=2)

    def test_an_unreachable_face_minimum_fails_loudly(self) -> None:
        spec = json.loads(json.dumps(SPEC))
        spec["minimum_bbox"]["Face"] = {"width": 4000, "height": 4000}
        with self.assertRaises(ValueError):
            _build(spec)

    def test_the_document_loads_as_a_contract(self) -> None:
        document = _build()
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "contract.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            parsed = contract.load(path)
        self.assertEqual(parsed.canvas, (SPEC["canvas"]["width"], SPEC["canvas"]["height"]))
        self.assertIn("Face", parsed.regions)
        for name in parsed.required_layers:
            self.assertIn(name, parsed.draw_order)

    def test_calibration_is_repeatable(self) -> None:
        self.assertEqual(_build(), _build())


if __name__ == "__main__":
    unittest.main()
