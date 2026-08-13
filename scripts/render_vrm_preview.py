from __future__ import annotations

import argparse
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from pipeline.tpose_vrm_layers import extract_tpose_sprites
from pipeline.vrm_layers import LayerSprite, flatten_sprites
from scripts.validate_vrm import read_glb

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = ROOT / "exports" / "vrm" / "mugi.vrm"
DEFAULT_SOURCE = (
    ROOT / "work" / "psd" / "tpose" / "mugi-tpose-source-v1-photoshop-pd2-preview.png"
)
DEFAULT_OUTPUT = ROOT / "docs" / "media" / "mugi-vrm-preview.gif"


def _background(size: tuple[int, int]) -> Image.Image:
    width, height = size
    image = Image.new("RGBA", size)
    pixels = image.load()
    for y in range(height):
        blend = y / max(height - 1, 1)
        color = (
            round(21 + 13 * blend),
            round(27 + 17 * blend),
            round(46 + 27 * blend),
            255,
        )
        for x in range(width):
            pixels[x, y] = color
    draw = ImageDraw.Draw(image, "RGBA")
    draw.ellipse((80, height - 74, width - 80, height - 30), fill=(4, 7, 16, 110))
    return image


def _expanded_alpha_box(
    image: Image.Image, padding_ratio: float = 0.025
) -> tuple[int, int, int, int]:
    alpha_box = image.getchannel("A").getbbox()
    if alpha_box is None:
        return (0, 0, image.width, image.height)
    padding_x = round((alpha_box[2] - alpha_box[0]) * padding_ratio)
    padding_y = round((alpha_box[3] - alpha_box[1]) * padding_ratio)
    return (
        max(0, alpha_box[0] - padding_x),
        max(0, alpha_box[1] - padding_y),
        min(image.width, alpha_box[2] + padding_x),
        min(image.height, alpha_box[3] + padding_y),
    )


def _pulse(index: int, center: int, radius: int) -> float:
    distance = abs(index - center)
    if distance >= radius:
        return 0.0
    return 0.5 + 0.5 * math.cos(math.pi * distance / radius)


def _transform(
    image: Image.Image,
    *,
    pivot: tuple[float, float],
    angle: float = 0.0,
    dx: float = 0.0,
    dy: float = 0.0,
    sx: float = 1.0,
    sy: float = 1.0,
) -> Image.Image:
    radians = math.radians(angle)
    cosine = math.cos(radians)
    sine = math.sin(radians)
    a = cosine / sx
    b = sine / sx
    d = -sine / sy
    e = cosine / sy
    pivot_x, pivot_y = pivot
    c = pivot_x - a * (pivot_x + dx) - b * (pivot_y + dy)
    f = pivot_y - d * (pivot_x + dx) - e * (pivot_y + dy)
    return image.transform(
        image.size,
        Image.Transform.AFFINE,
        (a, b, c, d, e, f),
        Image.Resampling.BICUBIC,
    )


def _prepare_layers(
    canvas_size: tuple[int, int],
    sprites: list[LayerSprite],
    crop_box: tuple[int, int, int, int],
    scale: float,
) -> dict[str, tuple[LayerSprite, Image.Image, tuple[float, float, float, float]]]:
    crop_left, crop_top, crop_right, crop_bottom = crop_box
    surface_size = (
        round((crop_right - crop_left) * scale),
        round((crop_bottom - crop_top) * scale),
    )
    prepared = {}
    for sprite in sprites:
        layer = Image.new("RGBA", surface_size)
        resized = (
            sprite.image.convert("RGBa")
            .resize(
                (
                    max(1, round(sprite.image.width * scale)),
                    max(1, round(sprite.image.height * scale)),
                ),
                Image.Resampling.LANCZOS,
            )
            .convert("RGBA")
        )
        red, green, blue, alpha = resized.split()
        rgb = Image.merge("RGB", (red, green, blue)).filter(
            ImageFilter.UnsharpMask(radius=0.6, percent=75, threshold=3)
        )
        resized = Image.merge("RGBA", (*rgb.split(), alpha))
        left = (sprite.canvas_box[0] - crop_left) * scale
        top = (sprite.canvas_box[1] - crop_top) * scale
        right = (sprite.canvas_box[2] - crop_left) * scale
        bottom = (sprite.canvas_box[3] - crop_top) * scale
        layer.alpha_composite(resized, (round(left), round(top)))
        prepared[sprite.name] = (sprite, layer, (left, top, right, bottom))
    return prepared


def _layer_motion(
    name: str,
    box: tuple[float, float, float, float],
    *,
    sway: float,
    breath: float,
    blink: float,
    mouth: float,
    gaze: float,
    gesture: float,
) -> tuple[dict[str, float | tuple[float, float]], bool]:
    left, top, right, bottom = box
    center = ((left + right) / 2, (top + bottom) / 2)
    motion: dict[str, float | tuple[float, float]] = {"pivot": center}
    visible = True
    if name == "torso":
        motion.update(
            pivot=((left + right) / 2, bottom),
            angle=0.28 * sway,
            sx=1 + 0.007 * breath,
            sy=1 + 0.004 * breath,
        )
    elif "arm" in name:
        direction = 1.0 if name == "screen_right_arm" else -1.0
        greeting = 4.0 * gesture if name == "screen_left_arm" else 0.0
        shoulder_x = left if name == "screen_right_arm" else right
        motion.update(
            pivot=(shoulder_x, (top + bottom) / 2),
            angle=direction * (60.0 + 2.0 * sway) + greeting,
        )
    elif "leg" in name:
        direction = -1.0 if name == "screen_right_leg" else 1.0
        motion.update(pivot=((left + right) / 2, top), angle=direction * 0.5 * sway)
    elif name in {"back_hair", "front_hair", "accessory"}:
        motion.update(pivot=((left + right) / 2, top), angle=-0.4 * sway)
    elif name in {"left_eye_white", "right_eye_white", "left_lashes", "right_lashes"}:
        motion.update(sy=max(0.1, 1.0 - 0.9 * blink))
    elif name in {"left_iris", "right_iris"}:
        motion.update(dx=2.2 * gaze, sy=max(0.1, 1.0 - 0.9 * blink))
    elif name == "mouth":
        motion.update(sx=1.0 + 0.03 * mouth, sy=1.0 + 0.9 * mouth)
    elif name == "mouth_inside":
        visible = mouth > 0.02
        motion.update(sx=1.0 + 0.03 * mouth, sy=0.2 + 1.8 * mouth)
    return motion, visible


def render_preview(
    model: Path,
    source: Path,
    output: Path,
    *,
    canvas_size: tuple[int, int] = (940, 720),
    frame_count: int = 80,
) -> None:
    read_glb(model)
    source_size, sprites = extract_tpose_sprites(source)
    flattened = flatten_sprites(source_size, sprites)
    crop_box = _expanded_alpha_box(flattened)
    max_width = canvas_size[0] - 72
    max_height = canvas_size[1] - 78
    scale = min(
        max_width / (crop_box[2] - crop_box[0]),
        max_height / (crop_box[3] - crop_box[1]),
    )
    prepared = _prepare_layers(source_size, sprites, crop_box, scale)
    surface_size = next(iter(prepared.values()))[1].size
    head_box = prepared["head"][2]
    head_pivot = ((head_box[0] + head_box[2]) / 2, head_box[3])
    head_parts = {
        "head",
        "face_cleanup",
        "left_eye_white",
        "right_eye_white",
        "left_iris",
        "right_iris",
        "left_lashes",
        "right_lashes",
        "mouth_inside",
        "mouth",
    }
    background = _background(canvas_size)
    frames: list[Image.Image] = []
    for index in range(frame_count):
        phase = 2.0 * math.pi * index / frame_count
        sway = math.sin(phase)
        breath = 0.5 - 0.5 * math.cos(phase)
        blink = max(
            _pulse(index, round(frame_count * 0.22), 3),
            _pulse(index, round(frame_count * 0.78), 3),
        )
        mouth = 0.65 * max(
            _pulse(index, round(frame_count * 0.39), 6),
            _pulse(index, round(frame_count * 0.56), 5),
        )
        gaze = math.sin(phase) * 0.9
        gesture = _pulse(index, round(frame_count * 0.62), 11)
        character = Image.new("RGBA", surface_size)
        for sprite in sorted(sprites, key=lambda item: item.depth):
            _, layer, box = prepared[sprite.name]
            motion, visible = _layer_motion(
                sprite.name,
                box,
                sway=sway,
                breath=breath,
                blink=blink,
                mouth=mouth,
                gaze=gaze,
                gesture=gesture,
            )
            if visible:
                animated_layer = _transform(layer, **motion)
                if sprite.name in head_parts:
                    animated_layer = _transform(
                        animated_layer,
                        pivot=head_pivot,
                        angle=0.65 * sway,
                        dx=0.7 * sway,
                        dy=-1.4 * breath,
                    )
                character.alpha_composite(animated_layer)
        frame = background.copy()
        x = (canvas_size[0] - character.width) // 2
        y = canvas_size[1] - character.height - 42
        frame.alpha_composite(character, (x, y))
        frames.append(frame.convert("P", palette=Image.Palette.ADAPTIVE, colors=192))
    output.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        output,
        save_all=True,
        append_images=frames[1:],
        duration=50,
        loop=0,
        disposal=2,
        optimize=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render a layered README preview from the Mugi VRM"
    )
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    render_preview(args.model.resolve(), args.source.resolve(), args.output.resolve())
    print(f"VRM preview written: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
