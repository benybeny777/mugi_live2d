from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from scripts.complete_hiyori_face import EYES, complete_face_layers


class CompleteHiyoriFaceTest(unittest.TestCase):
    def test_generates_every_independent_eye_and_mouth_layer(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = Image.new("RGBA", (1800, 900), (252, 236, 218, 255))
            draw = ImageDraw.Draw(source)
            for spec in EYES:
                cx, cy = spec.center
                rx, ry = spec.radii
                draw.ellipse(
                    (cx - rx, cy - ry, cx + rx, cy + ry),
                    fill=(252, 249, 240, 255),
                    outline=(25, 18, 13, 255),
                    width=10,
                )
                draw.ellipse(
                    (cx - 45, cy - 65, cx + 45, cy + 65),
                    fill=(25, 130, 90, 255),
                    outline=(8, 15, 10, 255),
                    width=7,
                )
                draw.ellipse((cx - 16, cy - 35, cx + 4, cy - 15), fill=(255, 255, 250, 255))
            draw.arc((1450, 740, 1520, 770), 10, 170, fill=(120, 76, 63, 255), width=4)
            source_path = root / "source.png"
            source.save(source_path)

            evidence = complete_face_layers(source_path, root / "layers")

            expected = [
                "左白目",
                "右白目",
                "左まつげ3",
                "右まつげ4",
                "唇",
                "上口",
                "下口",
                "口中",
                "口ハイライト",
            ]
            for display_name in expected:
                self.assertGreater(evidence["layers"][display_name]["pixels"], 0)
            self.assertIsNotNone(
                Image.open(root / "layers/EyeWhiteL.png").getchannel("A").getbbox()
            )
            self.assertEqual(
                np.count_nonzero(
                    np.asarray(Image.open(root / "layers/EyelashL.png").getchannel("A"))
                ),
                0,
            )


if __name__ == "__main__":
    unittest.main()
