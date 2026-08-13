from __future__ import annotations

from pathlib import Path

from pipeline.vrm_layers import (
    _scaled_split_coordinates,
    extract_layer_sprites,
    flatten_sprites,
)

ROOT = Path(__file__).resolve().parents[1]
PSD = ROOT / "work" / "psd" / "hiyori" / "mugi-hiyori-compatible-final.psd"


def test_split_coordinates_scale_with_resized_psd() -> None:
    assert _scaled_split_coordinates((2976, 4175)) == (1488, 2230, 2420)
    assert _scaled_split_coordinates((5952, 8350)) == (2976, 4460, 4840)


def test_final_psd_produces_expected_vrm_sprites() -> None:
    canvas_size, sprites = extract_layer_sprites(PSD)

    assert canvas_size == (2976, 4175)
    assert [sprite.name for sprite in sprites] == [
        "back_hair",
        "screen_left_leg",
        "screen_right_leg",
        "screen_left_arm",
        "screen_right_arm",
        "torso",
        "neck",
        "face",
        "left_eye_white",
        "right_eye_white",
        "left_iris",
        "right_iris",
        "left_lashes",
        "right_lashes",
        "mouth_inside",
        "mouth",
        "front_hair",
        "accessory",
    ]
    assert {sprite.bone for sprite in sprites} >= {
        "head",
        "spine",
        "leftUpperArm",
        "rightUpperArm",
        "leftUpperLeg",
        "rightUpperLeg",
    }
    assert all(sprite.image.getchannel("A").getbbox() is not None for sprite in sprites)
    assert flatten_sprites(canvas_size, sprites).getchannel("A").getbbox() == (
        660,
        93,
        2316,
        3997,
    )
