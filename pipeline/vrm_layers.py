from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from PIL import Image, ImageChops, ImageDraw
from psd_tools import PSDImage
from psd_tools.api.layers import Layer

REFERENCE_CANVAS_SIZE = (2976, 4175)
CANVAS_CENTER_X = 1488
LEG_SPLIT_TOP = 2230
TORSO_SPLIT_BOTTOM = 2420


@dataclass(frozen=True)
class LayerSprite:
    name: str
    bone: str
    depth: float
    image: Image.Image
    canvas_box: tuple[int, int, int, int]
    rest_visible: bool = True


def _layer_paths(psd: PSDImage) -> dict[str, Layer]:
    result: dict[str, Layer] = {}

    def visit(group: PSDImage | Layer, prefix: str = "") -> None:
        for layer in cast(Iterable[Layer], group):
            path = f"{prefix}/{layer.name}"
            if layer.is_group():
                visit(layer, path)
            else:
                result[path] = layer

    visit(psd)
    return result


def _composite_layers(
    canvas_size: tuple[int, int],
    layers: dict[str, Layer],
    paths: list[str],
    *,
    ignore_opacity: bool = False,
) -> Image.Image:
    canvas = Image.new("RGBA", canvas_size)
    for path in paths:
        layer = layers.get(path)
        if layer is None or (layer.opacity == 0 and not ignore_opacity):
            continue
        rendered = layer.topil() if ignore_opacity else layer.composite(force=True)
        if rendered is None:
            continue
        canvas.alpha_composite(rendered.convert("RGBA"), (layer.left, layer.top))
    return canvas


def _masked(image: Image.Image, box: tuple[int, int, int, int]) -> Image.Image:
    mask = Image.new("L", image.size)
    ImageDraw.Draw(mask).rectangle(box, fill=255)
    result = image.copy()
    result.putalpha(ImageChops.multiply(image.getchannel("A"), mask))
    return result


def _scaled_split_coordinates(canvas_size: tuple[int, int]) -> tuple[int, int, int]:
    """Scale body split guides from the approved source canvas to a resized PSD."""
    width_scale = canvas_size[0] / REFERENCE_CANVAS_SIZE[0]
    height_scale = canvas_size[1] / REFERENCE_CANVAS_SIZE[1]
    return (
        round(CANVAS_CENTER_X * width_scale),
        round(LEG_SPLIT_TOP * height_scale),
        round(TORSO_SPLIT_BOTTOM * height_scale),
    )


def _sprite(
    name: str,
    bone: str,
    depth: float,
    image: Image.Image,
    *,
    rest_visible: bool = True,
) -> LayerSprite:
    alpha_box = image.getchannel("A").getbbox()
    if alpha_box is None:
        raise ValueError(f"VRM layer {name} has no visible pixels")
    return LayerSprite(name, bone, depth, image.crop(alpha_box), alpha_box, rest_visible)


def extract_layer_sprites(psd_path: Path) -> tuple[tuple[int, int], list[LayerSprite]]:
    psd = PSDImage.open(psd_path)
    canvas_size = psd.size
    layers = _layer_paths(psd)
    center_x, leg_split_top, torso_split_bottom = _scaled_split_coordinates(canvas_size)

    body = _composite_layers(canvas_size, layers, ["/身体/体"])
    torso = _masked(body, (0, 0, canvas_size[0], torso_split_bottom))
    screen_left_leg = _masked(body, (0, leg_split_top, center_x, canvas_size[1]))
    screen_right_leg = _masked(
        body, (center_x, leg_split_top, canvas_size[0], canvas_size[1])
    )

    back_hair = _composite_layers(
        canvas_size,
        layers,
        [
            "/髪（後ろ）/後ろ髪",
            "/髪（後ろ）/左はね髪",
            "/髪（後ろ）/右はね髪",
        ],
    )
    screen_left_arm = _composite_layers(canvas_size, layers, ["/身体/左腕"])
    screen_right_arm = _composite_layers(canvas_size, layers, ["/身体/右腕"])
    neck = _composite_layers(canvas_size, layers, ["/身体/首"])
    face = _composite_layers(
        canvas_size,
        layers,
        [
            "/顔/左耳",
            "/顔/右耳",
            "/顔/顔下地",
            "/顔/顔",
            "/顔/左眉",
            "/顔/右眉",
            "/顔/鼻",
        ],
    )
    left_eye_white = _composite_layers(canvas_size, layers, ["/顔/左白目"])
    right_eye_white = _composite_layers(canvas_size, layers, ["/顔/右白目"])
    left_iris = _composite_layers(canvas_size, layers, ["/顔/左瞳", "/顔/左ハイライト"])
    right_iris = _composite_layers(canvas_size, layers, ["/顔/右瞳", "/顔/右ハイライト"])
    left_lashes = _composite_layers(
        canvas_size, layers, [f"/顔/左まつげ{index}" for index in range(1, 7)]
    )
    right_lashes = _composite_layers(
        canvas_size, layers, [f"/顔/右まつげ{index}" for index in range(1, 8)]
    )
    mouth = _composite_layers(canvas_size, layers, ["/顔/唇", "/顔/上口", "/顔/下口"])
    mouth_inside = _composite_layers(
        canvas_size, layers, ["/顔/口中", "/顔/口ハイライト"], ignore_opacity=True
    )
    front_hair = _composite_layers(
        canvas_size,
        layers,
        [
            "/髪（前・横）/前髪左",
            "/髪（前・横）/前髪右",
            "/髪（前・横）/前髪",
            "/髪（後ろ）/アホ毛",
        ],
    )
    accessory = _composite_layers(canvas_size, layers, ["/アクセサリー/装飾"])

    sprites = [
        _sprite("back_hair", "head", -0.040, back_hair),
        _sprite("screen_left_leg", "rightUpperLeg", -0.030, screen_left_leg),
        _sprite("screen_right_leg", "leftUpperLeg", -0.030, screen_right_leg),
        _sprite("screen_left_arm", "rightUpperArm", -0.020, screen_left_arm),
        _sprite("screen_right_arm", "leftUpperArm", -0.020, screen_right_arm),
        _sprite("torso", "spine", -0.010, torso),
        _sprite("neck", "head", 0.000, neck),
        _sprite("face", "head", 0.010, face),
        _sprite("left_eye_white", "head", 0.020, left_eye_white),
        _sprite("right_eye_white", "head", 0.020, right_eye_white),
        _sprite("left_iris", "head", 0.021, left_iris),
        _sprite("right_iris", "head", 0.021, right_iris),
        _sprite("left_lashes", "head", 0.022, left_lashes),
        _sprite("right_lashes", "head", 0.022, right_lashes),
        _sprite("mouth_inside", "head", 0.024, mouth_inside, rest_visible=False),
        _sprite("mouth", "head", 0.025, mouth),
        _sprite("front_hair", "head", 0.030, front_hair),
        _sprite("accessory", "head", 0.040, accessory),
    ]
    return canvas_size, sprites


def flatten_sprites(canvas_size: tuple[int, int], sprites: list[LayerSprite]) -> Image.Image:
    canvas = Image.new("RGBA", canvas_size)
    for sprite in sorted(sprites, key=lambda item: item.depth):
        if not sprite.rest_visible:
            continue
        canvas.alpha_composite(sprite.image, sprite.canvas_box[:2])
    return canvas
