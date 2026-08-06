from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw
from psd_tools import PSDImage
from psd_tools.api.layers import Layer

CANVAS_CENTER_X = 1488
LEG_SPLIT_TOP = 2230
TORSO_SPLIT_BOTTOM = 2420
ARM_ELBOW_RATIO = 0.44
ARM_WRIST_RATIO = 0.82
ARM_OVERLAP_PX = 24


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
        for layer in group:
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


def _arm_parts(
    image: Image.Image,
    side: str,
    bones: tuple[str, str, str],
) -> list[LayerSprite]:
    alpha_box = image.getchannel("A").getbbox()
    if alpha_box is None:
        raise ValueError(f"VRM {side} arm has no visible pixels")
    _, top, _, bottom = alpha_box
    height = bottom - top
    elbow = round(top + height * ARM_ELBOW_RATIO)
    wrist = round(top + height * ARM_WRIST_RATIO)
    bands = (
        ("upper_arm", bones[0], top, elbow + ARM_OVERLAP_PX, -0.0200),
        ("forearm", bones[1], elbow - ARM_OVERLAP_PX, wrist + ARM_OVERLAP_PX, -0.0195),
        ("hand", bones[2], wrist - ARM_OVERLAP_PX, bottom, -0.0190),
    )
    return [
        _sprite(
            f"screen_{side}_{part}",
            bone,
            depth,
            _masked(image, (0, band_top, image.width, band_bottom)),
        )
        for part, bone, band_top, band_bottom, depth in bands
    ]


def extract_layer_sprites(psd_path: Path) -> tuple[tuple[int, int], list[LayerSprite]]:
    psd = PSDImage.open(psd_path)
    canvas_size = psd.size
    layers = _layer_paths(psd)

    body = _composite_layers(canvas_size, layers, ["/身体/体"])
    torso = _masked(body, (0, 0, canvas_size[0], TORSO_SPLIT_BOTTOM))
    screen_left_leg = _masked(body, (0, LEG_SPLIT_TOP, CANVAS_CENTER_X, canvas_size[1]))
    screen_right_leg = _masked(
        body, (CANVAS_CENTER_X, LEG_SPLIT_TOP, canvas_size[0], canvas_size[1])
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
    screen_left_arm_parts = _arm_parts(
        screen_left_arm,
        "left",
        ("rightUpperArm", "rightLowerArm", "rightHand"),
    )
    screen_right_arm_parts = _arm_parts(
        screen_right_arm,
        "right",
        ("leftUpperArm", "leftLowerArm", "leftHand"),
    )
    neck = _composite_layers(canvas_size, layers, ["/身体/首"])
    face = _composite_layers(
        canvas_size,
        layers,
        [
            "/顔/左耳",
            "/顔/右耳",
            "/顔/顔下地",
            "/顔/顔",
            "/顔/鼻",
        ],
    )
    left_brow = _composite_layers(canvas_size, layers, ["/顔/左眉"])
    right_brow = _composite_layers(canvas_size, layers, ["/顔/右眉"])
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
    left_smile_crease = _composite_layers(
        canvas_size, layers, ["/顔/左笑い目くぼみ"], ignore_opacity=True
    )
    right_smile_crease = _composite_layers(
        canvas_size, layers, ["/顔/右笑い目くぼみ"], ignore_opacity=True
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
        *screen_left_arm_parts,
        *screen_right_arm_parts,
        _sprite("torso", "spine", -0.010, torso),
        _sprite("neck", "head", 0.000, neck),
        _sprite("face", "head", 0.010, face),
        _sprite("left_eye_white", "head", 0.020, left_eye_white),
        _sprite("right_eye_white", "head", 0.020, right_eye_white),
        _sprite("left_iris", "head", 0.021, left_iris),
        _sprite("right_iris", "head", 0.021, right_iris),
        _sprite("left_lashes", "head", 0.022, left_lashes),
        _sprite("right_lashes", "head", 0.022, right_lashes),
        _sprite("left_brow", "head", 0.023, left_brow),
        _sprite("right_brow", "head", 0.023, right_brow),
        _sprite(
            "left_smile_crease", "head", 0.0235, left_smile_crease, rest_visible=False
        ),
        _sprite(
            "right_smile_crease", "head", 0.0235, right_smile_crease, rest_visible=False
        ),
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
