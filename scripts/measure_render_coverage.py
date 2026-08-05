"""Measure hair coverage defects from a rendered viewer screenshot.

Two defects trade against each other and must be judged together:

* holes -- the stage background showing through gaps between hair ArtMeshes.
* lost decorations -- a fill closing the holes also closes the transparent gaps
  that give the braid and the hairclip their shape, turning them into a blob.

Optimising either alone produces a model that looks worse overall, so this
module reports both from the same render.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from PIL import Image

# The viewer stage is a smooth vertical gradient, so the reference colour has to
# be sampled per row rather than taken as a single constant. The column must sit
# inside the stage card and left of the character; column 3 is the dark page
# background outside the card, which would make every hole test fail.
BACKGROUND_COLUMN = 40
BACKGROUND_TOLERANCE = 2


@dataclass(frozen=True)
class CoverageMetric:
    roi_pixels: int
    hole_pixels: int
    hole_percent: float
    star_pixels: int
    clip_pixels: int


def background_reference(pixels: np.ndarray, column: int = BACKGROUND_COLUMN) -> np.ndarray:
    """Per-row stage colour, taken from a column the character never covers."""
    if column >= pixels.shape[1]:
        raise ValueError(f"background column {column} is outside the image")
    return pixels[:, column, :3].astype(np.int16)


def hole_mask(
    pixels: np.ndarray,
    roi: tuple[int, int, int, int],
    tolerance: int = BACKGROUND_TOLERANCE,
    column: int = BACKGROUND_COLUMN,
) -> np.ndarray:
    """Pixels inside the ROI that still show the stage background."""
    top, left, height, width = roi
    reference = background_reference(pixels, column)[top : top + height][:, None, :]
    region = pixels[top : top + height, left : left + width, :3].astype(np.int16)
    return np.abs(region - reference).max(axis=2) <= tolerance


def star_mask(region: np.ndarray) -> np.ndarray:
    """Saturated orange of the star hairclip."""
    red, green, blue = region[:, :, 0], region[:, :, 1], region[:, :, 2]
    return (red > 200) & (green > 130) & (green < 220) & (blue < 130)


def clip_mask(region: np.ndarray) -> np.ndarray:
    """Green of the bar hairclip; green must lead both other channels."""
    red, green, blue = region[:, :, 0], region[:, :, 1], region[:, :, 2]
    return (green > 80) & (green - red > 12) & (green - blue > 12)


def measure(
    path: Path,
    roi: tuple[int, int, int, int],
    column: int = BACKGROUND_COLUMN,
) -> CoverageMetric:
    pixels = np.asarray(Image.open(path).convert("RGB"))
    top, left, height, width = roi
    if top + height > pixels.shape[0] or left + width > pixels.shape[1]:
        raise ValueError(f"roi {roi} does not fit in image {pixels.shape[1]}x{pixels.shape[0]}")
    region = pixels[top : top + height, left : left + width, :3].astype(np.int16)
    holes = hole_mask(pixels, roi, column=column)
    total = height * width
    return CoverageMetric(
        roi_pixels=total,
        hole_pixels=int(holes.sum()),
        hole_percent=round(100 * float(holes.sum()) / total, 4),
        star_pixels=int(star_mask(region).sum()),
        clip_pixels=int(clip_mask(region).sum()),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("renders", nargs="+", type=Path)
    parser.add_argument("--roi", default="210,163,280,280", help="top,left,height,width")
    parser.add_argument("--background-column", type=int, default=BACKGROUND_COLUMN)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    roi = tuple(int(value) for value in args.roi.split(","))
    if len(roi) != 4:
        parser.error("--roi requires top,left,height,width")
    results = {}
    for path in args.renders:
        results[path.stem] = asdict(measure(path, roi, args.background_column))
    rendered = json.dumps(
        {"roi": list(roi), "background_column": args.background_column, "results": results},
        ensure_ascii=False,
        indent=2,
    )
    print(rendered)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
