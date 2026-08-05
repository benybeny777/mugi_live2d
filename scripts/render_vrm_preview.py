from __future__ import annotations

import argparse
import io
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance
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


def render_preview(
    model: Path,
    output: Path,
    *,
    canvas_size: tuple[int, int] = (520, 640),
    frame_count: int = 40,
) -> None:
    texture = extract_thumbnail(model)
    alpha_box = texture.getchannel("A").getbbox()
    if alpha_box is not None:
        texture = texture.crop(alpha_box)
    max_width = canvas_size[0] - 72
    max_height = canvas_size[1] - 78
    scale = min(max_width / texture.width, max_height / texture.height)
    texture = texture.resize(
        (round(texture.width * scale), round(texture.height * scale)), Image.Resampling.LANCZOS
    )
    background = _background(canvas_size)
    frames: list[Image.Image] = []
    for index in range(frame_count):
        phase = 2.0 * math.pi * index / frame_count
        angle = math.radians(24.0 * math.sin(phase))
        width_scale = max(0.12, math.cos(angle))
        card_width = max(1, round(texture.width * width_scale))
        card = texture.resize((card_width, texture.height), Image.Resampling.LANCZOS)
        brightness = 0.92 + 0.08 * width_scale
        card = ImageEnhance.Brightness(card).enhance(brightness)
        frame = background.copy()
        x = (canvas_size[0] - card.width) // 2 + round(8 * math.sin(angle))
        y = canvas_size[1] - card.height - 42 + round(4 * math.cos(phase))
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
