from pathlib import Path

from pipeline.tpose_vrm_layers import extract_tpose_sprites
from pipeline.vrm_layers import flatten_sprites

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "work" / "psd" / "tpose" / "mugi-tpose-source-v1-photoshop-pd2-preview.png"


def test_tpose_source_produces_the_vrm_contract() -> None:
    canvas, sprites = extract_tpose_sprites(SOURCE)
    assert canvas == (2920, 4096)
    assert len(sprites) == 8
    assert [sprite.name for sprite in sprites][2:7] == [
        "screen_left_shoulder_underlay",
        "screen_right_shoulder_underlay",
        "screen_left_arm",
        "screen_right_arm",
        "torso",
    ]
    left_underlay, right_underlay, left, right = sprites[2:6]
    assert left_underlay.bone == "spine"
    assert right_underlay.bone == "spine"
    assert left.canvas_box[2] < canvas[0] // 2
    assert right.canvas_box[0] > canvas[0] // 2
    assert left.canvas_box[3] < round(canvas[1] * 0.35)
    assert right.canvas_box[3] < round(canvas[1] * 0.35)
    torso = sprites[6]
    assert torso.canvas_box[0] < left.canvas_box[2]
    assert torso.canvas_box[2] > right.canvas_box[0]
    assert left_underlay.canvas_box[2] > left.canvas_box[2]
    assert right_underlay.canvas_box[0] < right.canvas_box[0]
    assert flatten_sprites(canvas, sprites).getchannel("A").getbbox() is not None
