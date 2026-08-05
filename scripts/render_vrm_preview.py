from __future__ import annotations

import argparse
import io
import math
from pathlib import Path

from build_vrm import _morph_offset
from PIL import Image, ImageDraw
from validate_vrm import read_glb

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = ROOT / "exports" / "vrm" / "mugi.vrm"
DEFAULT_OUTPUT = ROOT / "docs" / "media" / "mugi-vrm-preview.gif"


def extract_thumbnail(model: Path) -> Image.Image:
    document, binary = read_glb(model)
    vrm = document["extensions"]["VRMC_vrm"]
    image_index = vrm["meta"]["thumbnailImage"]
    image = document["images"][image_index]
    view = document["bufferViews"][image["bufferView"]]
    start = view.get("byteOffset", 0)
    payload = binary[start : start + view["byteLength"]]
    with Image.open(io.BytesIO(payload)) as opened:
        return opened.convert("RGBA")


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


def _warp_card(
    card: Image.Image,
    *,
    crop_box: tuple[int, int, int, int],
    texture_size: tuple[int, int],
    weights: dict[str, float],
    mesh_columns: int = 32,
    mesh_rows: int = 48,
) -> Image.Image:
    texture_width, texture_height = texture_size
    crop_left, crop_top, crop_right, crop_bottom = crop_box
    crop_u = crop_left / texture_width
    crop_v = crop_top / texture_height
    crop_u_span = (crop_right - crop_left) / texture_width
    crop_v_span = (crop_bottom - crop_top) / texture_height
    model_height = 1.8
    model_width = model_height * texture_width / texture_height

    def source_point(x: float, y: float) -> tuple[float, float]:
        u = crop_u + (x / card.width) * crop_u_span
        v = crop_v + (y / card.height) * crop_v_span
        model_dx = 0.0
        model_dy = 0.0
        for name, weight in weights.items():
            if weight <= 0.0:
                continue
            dx, dy, _ = _morph_offset(name, u, v, model_width, model_height)
            model_dx += dx * weight
            model_dy += dy * weight
        pixel_dx = (model_dx / model_width) * card.width / crop_u_span
        pixel_dy = (-model_dy / model_height) * card.height / crop_v_span
        return x - pixel_dx, y - pixel_dy

    x_points = [round(card.width * index / mesh_columns) for index in range(mesh_columns + 1)]
    y_points = [round(card.height * index / mesh_rows) for index in range(mesh_rows + 1)]
    mesh = []
    for row in range(mesh_rows):
        top = y_points[row]
        bottom = y_points[row + 1]
        for column in range(mesh_columns):
            left = x_points[column]
            right = x_points[column + 1]
            upper_left = source_point(left, top)
            lower_left = source_point(left, bottom)
            lower_right = source_point(right, bottom)
            upper_right = source_point(right, top)
            mesh.append(
                (
                    (left, top, right, bottom),
                    (*upper_left, *lower_left, *lower_right, *upper_right),
                )
            )
    return card.transform(card.size, Image.Transform.MESH, mesh, Image.Resampling.BICUBIC)


def _pulse(index: int, center: int, radius: int) -> float:
    distance = abs(index - center)
    if distance >= radius:
        return 0.0
    return 0.5 + 0.5 * math.cos(math.pi * distance / radius)


def _animation_weights(index: int, frame_count: int) -> dict[str, float]:
    phase = 2.0 * math.pi * index / frame_count
    weights = {"breath": 0.5 + 0.5 * math.sin(phase - math.pi / 2.0)}
    blink = max(
        _pulse(index, round(frame_count * 0.22), 3), _pulse(index, round(frame_count * 0.78), 3)
    )
    if blink > 0.0:
        weights["blinkLeft"] = blink
        weights["blinkRight"] = blink
    mouth = _pulse(index, round(frame_count * 0.45), 7)
    if mouth > 0.0:
        weights["aa"] = 0.42 * mouth
    return weights


def render_preview(
    model: Path,
    output: Path,
    *,
    canvas_size: tuple[int, int] = (520, 640),
    frame_count: int = 80,
) -> None:
    texture = extract_thumbnail(model)
    texture_size = texture.size
    crop_box = _expanded_alpha_box(texture)
    texture = texture.crop(crop_box)
    max_width = canvas_size[0] - 72
    max_height = canvas_size[1] - 78
    scale = min(max_width / texture.width, max_height / texture.height)
    texture = texture.resize(
        (round(texture.width * scale), round(texture.height * scale)), Image.Resampling.LANCZOS
    )
    background = _background(canvas_size)
    frames: list[Image.Image] = []
    for index in range(frame_count):
        card = _warp_card(
            texture,
            crop_box=crop_box,
            texture_size=texture_size,
            weights=_animation_weights(index, frame_count),
        )
        frame = background.copy()
        x = (canvas_size[0] - card.width) // 2
        y = canvas_size[1] - card.height - 42
        frame.alpha_composite(card, (x, y))
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
    parser = argparse.ArgumentParser(description="Render a README preview from the Mugi VRM")
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    render_preview(args.model.resolve(), args.output.resolve())
    print(f"VRM preview written: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
