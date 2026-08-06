from __future__ import annotations

from pathlib import Path

from pipeline.vrm_layers import extract_layer_sprites, flatten_sprites

ROOT = Path(__file__).resolve().parents[1]
PSD = ROOT / "work" / "psd" / "hiyori" / "mugi-hiyori-compatible-final.psd"


def test_final_psd_produces_expected_vrm_sprites() -> None:
    canvas_size, sprites = extract_layer_sprites(PSD)

    assert canvas_size == (2976, 4175)
    assert [sprite.name for sprite in sprites] == [
        "back_hair",
        "screen_left_leg",
        "screen_right_leg",
        "screen_left_upper_arm",
        "screen_left_forearm",
        "screen_left_hand",
        "screen_right_upper_arm",
        "screen_right_forearm",
        "screen_right_hand",
        "torso",
        "neck",
        "face",
        "left_eye_white",
        "right_eye_white",
        "left_iris",
        "right_iris",
        "left_lashes",
        "right_lashes",
        "left_brow",
        "right_brow",
        "left_smile_crease",
        "right_smile_crease",
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
        "leftLowerArm",
        "rightLowerArm",
        "leftHand",
        "rightHand",
        "leftUpperLeg",
        "rightUpperLeg",
    }
    assert all(sprite.image.getchannel("A").getbbox() is not None for sprite in sprites)
    by_name = {sprite.name: sprite for sprite in sprites}
    for side in ("left", "right"):
        upper = by_name[f"screen_{side}_upper_arm"].canvas_box
        forearm = by_name[f"screen_{side}_forearm"].canvas_box
        hand = by_name[f"screen_{side}_hand"].canvas_box
        assert upper[3] > forearm[1]
        assert forearm[3] > hand[1]
    assert flatten_sprites(canvas_size, sprites).getchannel("A").getbbox() == (
        660,
        93,
        2316,
        3997,
    )
