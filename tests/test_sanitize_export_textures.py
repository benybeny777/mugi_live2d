from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from scripts.sanitize_export_textures import (
    dilate_region_alpha,
    fill_hair_cap_regions,
    fill_solid_rect,
    parse_atlas_layout,
    regions_from_moc_topology,
    remove_bright_neutral_regions,
)


def strands(width: int, gap: int) -> np.ndarray:
    """Two opaque bars separated by a transparent gap of ``gap`` pixels."""
    pixels = np.zeros((40, 60, 4), dtype=np.uint8)
    pixels[5:35, 10 : 10 + width] = (90, 60, 40, 255)
    pixels[5:35, 10 + width + gap : 10 + width + gap + width] = (90, 60, 40, 255)
    return pixels


def test_dilation_closes_a_thin_seam(tmp_path: Path) -> None:
    texture = tmp_path / "texture_00.png"
    Image.fromarray(strands(12, 4), "RGBA").save(texture)

    grown = dilate_region_alpha(texture, {"髪": (0, 0, 60, 40)}, {"髪"}, radius=3)
    result = np.array(Image.open(texture).convert("RGBA"))

    assert grown > 0
    # The 4px seam is bridged, so the two bars now read as one covered run.
    assert np.all(result[20, 10:38, 3] == 255)


def test_dilation_keeps_a_wide_intentional_gap_open(tmp_path: Path) -> None:
    texture = tmp_path / "texture_00.png"
    Image.fromarray(strands(12, 20), "RGBA").save(texture)

    dilate_region_alpha(texture, {"髪": (0, 0, 60, 40)}, {"髪"}, radius=3)
    result = np.array(Image.open(texture).convert("RGBA"))

    # A gap that defines the braid must survive; only its edges may thicken.
    assert result[20, 31, 3] == 0


def test_dilation_never_overwrites_existing_pixels(tmp_path: Path) -> None:
    texture = tmp_path / "texture_00.png"
    pixels = strands(12, 20)
    pixels[18:22, 12:16] = (250, 190, 60, 255)
    Image.fromarray(pixels, "RGBA").save(texture)

    dilate_region_alpha(texture, {"髪": (0, 0, 60, 40)}, {"髪"}, radius=5)
    result = np.array(Image.open(texture).convert("RGBA"))

    assert np.all(result[18:22, 12:16] == (250, 190, 60, 255))


def test_dilation_copies_a_neighbouring_colour(tmp_path: Path) -> None:
    texture = tmp_path / "texture_00.png"
    Image.fromarray(strands(12, 20), "RGBA").save(texture)

    dilate_region_alpha(texture, {"髪": (0, 0, 60, 40)}, {"髪"}, radius=2)
    result = np.array(Image.open(texture).convert("RGBA"))

    assert result[20, 23].tolist() == [90, 60, 40, 255]


def test_a_zero_radius_is_rejected(tmp_path: Path) -> None:
    texture = tmp_path / "texture_00.png"
    Image.fromarray(strands(12, 4), "RGBA").save(texture)
    with pytest.raises(ValueError):
        dilate_region_alpha(texture, {"髪": (0, 0, 60, 40)}, {"髪"}, radius=0)


def test_an_empty_region_is_rejected(tmp_path: Path) -> None:
    texture = tmp_path / "texture_00.png"
    Image.fromarray(np.zeros((40, 60, 4), dtype=np.uint8), "RGBA").save(texture)
    with pytest.raises(ValueError):
        dilate_region_alpha(texture, {"髪": (0, 0, 60, 40)}, {"髪"}, radius=3)


def test_topology_uvs_become_top_left_atlas_rectangles(tmp_path: Path) -> None:
    topology = tmp_path / "topology.json"
    topology.write_text(
        """{
          "schema": "mugi-live2d/moc-topology@1",
          "drawables": [
            {"id": "Hair", "parentPartId": "PartHair", "uvs": [0.25, 0.75, 0.5, 0.5]},
            {"id": "Eye", "parentPartId": "PartEye", "uvs": [0.0, 1.0, 0.1, 0.9]}
          ]
        }""",
        encoding="utf-8",
    )

    regions = regions_from_moc_topology(topology, (100, 200), {"PartHair"})

    assert regions == {"Hair": (25, 50, 25, 50)}


def test_topology_rejects_missing_parent_parts(tmp_path: Path) -> None:
    topology = tmp_path / "topology.json"
    topology.write_text(
        '{"schema":"mugi-live2d/moc-topology@1","drawables":[]}',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="no drawables"):
        regions_from_moc_topology(topology, (100, 100), {"PartHair"})


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


def test_hair_cap_fills_enclosed_interior_behind_face(tmp_path: Path) -> None:
    texture = tmp_path / "texture_00.png"
    pixels = np.zeros((100, 100, 4), dtype=np.uint8)
    pixels[10:20, 10:90] = (90, 60, 40, 255)
    pixels[10:85, 10:15] = (90, 60, 40, 255)
    pixels[10:85, 85:90] = (90, 60, 40, 255)
    Image.fromarray(pixels, "RGBA").save(texture)

    changed = fill_hair_cap_regions(texture, {"後ろ髪": (0, 0, 100, 100)}, {"後ろ髪"})
    result = np.array(Image.open(texture).convert("RGBA"))

    assert changed > 1000
    assert result[35, 50].tolist() == [90, 60, 40, 255]
    assert result[80, 50].tolist() == [90, 60, 40, 255]


def test_fill_solid_rect_is_limited_to_reserved_area(tmp_path: Path) -> None:
    texture = tmp_path / "texture_00.png"
    Image.new("RGBA", (8, 8)).save(texture)

    changed = fill_solid_rect(texture, (2, 1, 3, 4), (112, 84, 72))
    result = np.array(Image.open(texture).convert("RGBA"))

    assert changed == 12
    assert result[1, 2].tolist() == [112, 84, 72, 255]
    assert result[5, 2].tolist() == [0, 0, 0, 0]
