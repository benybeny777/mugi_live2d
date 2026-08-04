from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from scripts.fixed_topology_qa import validate


class FixedTopologyQaTest(unittest.TestCase):
    def test_rejects_tiny_face_and_missing_parts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            topology = root / "topology.json"
            topology.write_text(json.dumps({
                "id": "test", "canvas": {"width": 100, "height": 100},
                "required_layers": ["Face", "HairFront"], "optional_layers": [],
                "minimum_bbox": {"Face": {"width": 50, "height": 50}},
                "containment": [], "overlap": []
            }), encoding="utf-8")
            image = Image.new("RGBA", (100, 100))
            ImageDraw.Draw(image).rectangle((10, 10, 20, 20), fill="white")
            image.save(root / "Face.png")
            report = validate(root, topology)
            self.assertFalse(report["passed"])
            self.assertTrue(any("bbox" in item for item in report["failures"]))
            self.assertTrue(any("HairFront" in item for item in report["failures"]))


if __name__ == "__main__":
    unittest.main()
