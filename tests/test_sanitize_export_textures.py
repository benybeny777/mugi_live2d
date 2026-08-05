from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from scripts.sanitize_export_textures import (
    parse_atlas_layout,
    remove_bright_neutral_regions,
)


def test_region_cleanup_does_not_touch_skin_outside_hair(tmp_path: Path) -> None:
    texture = tmp_path / "texture_00.png"
    pixels = np.zeros((8, 8, 4), dtype=np.uint8)
    pixels[1:4, 1:4] = (240, 235, 230, 255)
    pixels[5:7, 5:7] = (240, 235, 230, 255)
    Image.fromarray(pixels, "RGBA").save(texture)
    layout = tmp_path / "layout.tsv"
    layout.write_text("atlas=8x8\nname=前髪\tx=1\ty=1\tw=3\th=3\n", encoding="utf-8")

    regions = parse_atlas_layout(layout)
    removed = remove_bright_neutral_regions(texture, regions, {"前髪"})
    result = np.array(Image.open(texture).convert("RGBA"))

    assert removed == 9
    assert result[1:4, 1:4, 3].sum() == 0
    assert np.all(result[5:7, 5:7] == (240, 235, 230, 255))
