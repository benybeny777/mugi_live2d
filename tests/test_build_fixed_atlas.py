from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from scripts.build_fixed_atlas import build


class FixedAtlasBuilderTest(unittest.TestCase):
    def test_projects_semantic_plate_into_uv_triangle(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            parts = root / "parts"
            parts.mkdir()
            plate = Image.new("RGBA", (100, 100))
            ImageDraw.Draw(plate).rectangle((20, 20, 80, 80), fill=(70, 150, 90, 255))
            plate.save(parts / "PartFace.png")
            manifest = {
                "canvas": {"width": 100, "height": 100},
                "parts": {"PartFace": {"file": "PartFace.png", "bbox": [20, 20, 81, 81]}},
            }
            (parts / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            topology = {
                "canvas": {
                    "width": 100,
                    "height": 100,
                    "originX": 50,
                    "originY": 50,
                    "pixelsPerUnit": 100,
                },
                "drawables": [
                    {
                        "id": "FaceMesh",
                        "parentPartId": "PartFace",
                        "positions": [-0.3, 0.3, 0.3, 0.3, 0.0, -0.3],
                        "uvs": [0.1, 0.9, 0.9, 0.9, 0.5, 0.1],
                        "indices": [0, 1, 2],
                    }
                ],
            }
            topology_path = root / "topology.json"
            topology_path.write_text(json.dumps(topology), encoding="utf-8")
            reference = root / "reference.png"
            Image.new("RGBA", (64, 64)).save(reference)
            output = root / "atlas.png"

            report = build(topology_path, parts / "manifest.json", reference, output)

            self.assertEqual(report["triangles"], 1)
            self.assertEqual(report["drawable_count"], 1)
            self.assertGreater(Image.open(output).getchannel("A").getbbox()[2], 30)

    def test_sparse_hair_plate_preserves_reference_fill(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            parts = root / "parts"
            parts.mkdir()
            # A sparse streak represents one Mugi hair plate. The surrounding
            # reference colour must survive instead of becoming transparent.
            plate = Image.new("RGBA", (100, 100))
            ImageDraw.Draw(plate).rectangle((45, 20, 55, 80), fill=(90, 55, 35, 255))
            plate.save(parts / "PartHairFront.png")
            manifest = {
                "canvas": {"width": 100, "height": 100},
                "parts": {
                    "PartHairFront": {
                        "file": "PartHairFront.png",
                        "bbox": [45, 20, 56, 81],
                    }
                },
            }
            (parts / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            topology = {
                "canvas": {
                    "width": 100,
                    "height": 100,
                    "originX": 50,
                    "originY": 50,
                    "pixelsPerUnit": 100,
                },
                "drawables": [
                    {
                        "id": "HairMesh",
                        "parentPartId": "PartHairFront",
                        "positions": [-0.3, 0.3, 0.3, 0.3, 0.0, -0.3],
                        "uvs": [0.1, 0.9, 0.9, 0.9, 0.5, 0.1],
                        "indices": [0, 1, 2],
                    }
                ],
            }
            topology_path = root / "topology.json"
            topology_path.write_text(json.dumps(topology), encoding="utf-8")
            reference = root / "reference.png"
            Image.new("RGBA", (64, 64), (60, 60, 60, 255)).save(reference)
            output = root / "atlas.png"

            build(topology_path, parts / "manifest.json", reference, output)

            result = Image.open(output).convert("RGBA")
            self.assertEqual(result.getpixel((16, 16))[3], 255)
            self.assertEqual(result.getpixel((48, 16))[3], 255)


if __name__ == "__main__":
    unittest.main()
