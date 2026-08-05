"""Keep only plausible brown hair pixels in a reserved atlas rectangle."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--rect", default="4096,0,2048,2048")
    parser.add_argument(
        "--clear-rect",
        action="append",
        default=[],
        help="reserved-region x0,y0,x1,y1 to keep fully transparent",
    )
    parser.add_argument("--protect-accessories-radius", type=int, default=0)
    args = parser.parse_args()

    left, top, width, height = (int(value) for value in args.rect.split(","))
    atlas = Image.open(args.input).convert("RGBA")
    pixels = np.asarray(atlas).copy()
    region = pixels[top : top + height, left : left + width]
    red = region[:, :, 0].astype(np.int16)
    green = region[:, :, 1].astype(np.int16)
    blue = region[:, :, 2].astype(np.int16)
    alpha = region[:, :, 3]

    # Mugi's hair palette is muted brown. These broad bounds retain highlights
    # and dark outlines while rejecting transparent-black mesh artifacts, skin,
    # green clips, and the yellow star. The original 48 meshes remain above the
    # underlay, so rejected pixels reveal the correct existing art.
    hair = (
        (alpha > 8)
        & (red >= 32)
        & (red <= 205)
        & (green >= 20)
        & (green <= 175)
        & (blue >= 15)
        & (blue <= 155)
        & (red * 10 >= green * 9)
        & (green * 10 >= blue * 8)
    )
    accessory_pixels = 0
    protected_pixels = 0
    if args.protect_accessories_radius > 0:
        # Star: warm saturated yellow. Hair clips: saturated green. Restrict
        # detection to the right half where these accessories live so eyes and
        # skin highlights can never become protection seeds.
        yy, xx = np.ogrid[:height, :width]
        right_side = xx >= width // 2
        yellow = (
            (alpha > 8)
            & (red >= 175)
            & (green >= 105)
            & (blue <= 135)
            & (red >= green)
            & right_side
        )
        green_clip = (
            (alpha > 8)
            & (green >= 65)
            & (green * 10 >= red * 12)
            & (green * 10 >= blue * 11)
            & right_side
        )
        accessories = yellow | green_clip
        accessory_pixels = int(np.count_nonzero(accessories))
        protected = ndimage.binary_dilation(
            accessories, iterations=args.protect_accessories_radius
        )
        protected_pixels = int(np.count_nonzero(protected))
        hair &= ~protected
    cleared: list[list[int]] = []
    for value in args.clear_rect:
        x0, y0, x1, y1 = (int(item) for item in value.split(","))
        if not (0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height):
            raise ValueError(f"clear rectangle outside reserve: {value}")
        hair[y0:y1, x0:x1] = False
        cleared.append([x0, y0, x1, y1])
    before = int(np.count_nonzero(alpha > 8))
    kept = int(np.count_nonzero(hair))
    region[:, :, 3] = np.where(hair, alpha, 0).astype(np.uint8)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(pixels, "RGBA").save(args.output)
    result = {
        "input": str(args.input),
        "output": str(args.output),
        "rect": [left, top, width, height],
        "opaque_before": before,
        "hair_pixels_kept": kept,
        "pixels_removed": before - kept,
        "clear_rects": cleared,
        "accessory_seed_pixels": accessory_pixels,
        "accessory_protected_pixels": protected_pixels,
        "protect_accessories_radius": args.protect_accessories_radius,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
