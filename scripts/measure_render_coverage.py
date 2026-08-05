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
from scipy.ndimage import label

# The viewer stage is a smooth vertical gradient, so the reference colour has to
# be sampled per row rather than taken as a single constant. The column must sit
# inside the stage card and left of the character; column 3 is the dark page
# background outside the card, which would make every hole test fail.
BACKGROUND_COLUMN = 40
BACKGROUND_TOLERANCE = 2


@dataclass(frozen=True)
class CoverageMetric:
    roi: tuple[int, int, int, int]
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


def character_bounds(
    pixels: np.ndarray,
    stage: tuple[int, int, int, int],
    tolerance: int = BACKGROUND_TOLERANCE,
    column: int = BACKGROUND_COLUMN,
) -> tuple[int, int, int, int]:
    """Bounding box of everything drawn over the stage, as top,left,height,width.

    Candidates do not all render the character at the same position or scale, so
    a fixed rectangle silently drops decorations out of frame and makes the
    counts incomparable. Anchoring to the drawn silhouette keeps them comparable.
    Holes lie inside this box by construction: they are enclosed by the parts
    that do differ from the background.
    """
    top, left, height, width = stage
    reference = background_reference(pixels, column)[top : top + height][:, None, :]
    region = pixels[top : top + height, left : left + width, :3].astype(np.int16)
    drawn = np.abs(region - reference).max(axis=2) > tolerance
    rows = np.flatnonzero(drawn.any(axis=1))
    columns = np.flatnonzero(drawn.any(axis=0))
    if not rows.size or not columns.size:
        raise ValueError("no character was drawn over the stage")
    return (
        top + int(rows[0]),
        left + int(columns[0]),
        int(rows[-1] - rows[0]) + 1,
        int(columns[-1] - columns[0]) + 1,
    )


def head_bounds(
    pixels: np.ndarray,
    stage: tuple[int, int, int, int],
    head_fraction: float = 0.35,
    column: int = BACKGROUND_COLUMN,
) -> tuple[int, int, int, int]:
    """Top slice of the character box, covering the hair and its decorations.

    Measuring the whole character is useless here: the green ribbon swamps the
    hairclip count by two orders of magnitude. Taking a fixed fraction of the
    character box keeps the region on the head wherever the character renders.
    """
    top, left, height, width = character_bounds(pixels, stage, column=column)
    return (top, left, max(1, int(round(height * head_fraction))), width)


def interior_hole_mask(background: np.ndarray) -> np.ndarray:
    """Background pixels enclosed by the drawing, excluding the space around it.

    Empty space beside the head is not a defect; background seen *through* the
    hair is. Everything reachable from the region border is outside space, so
    only the unreachable background components are counted.
    """
    labels, count = label(background)
    if count == 0:
        return np.zeros_like(background)
    outside = set(labels[0, :]) | set(labels[-1, :]) | set(labels[:, 0]) | set(labels[:, -1])
    outside.discard(0)
    return background & ~np.isin(labels, list(outside))


def star_mask(region: np.ndarray) -> np.ndarray:
    """Saturated orange of the star hairclip."""
    red, green, blue = region[:, :, 0], region[:, :, 1], region[:, :, 2]
    return (red > 200) & (green > 130) & (green < 220) & (blue < 130)


def clip_mask(region: np.ndarray) -> np.ndarray:
    """Green of the bar hairclip; green must lead both other channels.

    The stage background is itself a pale green that satisfies the channel
    ordering, so the clip is additionally required to be darker than the stage.
    """
    red, green, blue = region[:, :, 0], region[:, :, 1], region[:, :, 2]
    return (green > 80) & (green < 200) & (green - red > 12) & (green - blue > 12)


def measure(
    path: Path,
    stage: tuple[int, int, int, int],
    column: int = BACKGROUND_COLUMN,
    head_fraction: float = 0.35,
) -> CoverageMetric:
    pixels = np.asarray(Image.open(path).convert("RGB"))
    top, left, height, width = stage
    if top + height > pixels.shape[0] or left + width > pixels.shape[1]:
        raise ValueError(f"stage {stage} does not fit in image {pixels.shape[1]}x{pixels.shape[0]}")
    roi = head_bounds(pixels, stage, head_fraction, column)
    top, left, height, width = roi
    region = pixels[top : top + height, left : left + width, :3].astype(np.int16)
    holes = interior_hole_mask(hole_mask(pixels, roi, column=column))
    total = height * width
    return CoverageMetric(
        roi=roi,
        roi_pixels=total,
        hole_pixels=int(holes.sum()),
        hole_percent=round(100 * float(holes.sum()) / total, 4),
        star_pixels=int(star_mask(region).sum()),
        clip_pixels=int(clip_mask(region).sum()),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("renders", nargs="+", type=Path)
    parser.add_argument(
        "--stage",
        default="118,40,1220,510",
        help="search window over the viewer stage card: top,left,height,width",
    )
    parser.add_argument("--background-column", type=int, default=BACKGROUND_COLUMN)
    parser.add_argument("--head-fraction", type=float, default=0.35)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    stage = tuple(int(value) for value in args.stage.split(","))
    if len(stage) != 4:
        parser.error("--stage requires top,left,height,width")
    results = {}
    for path in args.renders:
        results[path.stem] = asdict(
            measure(path, stage, args.background_column, args.head_fraction)
        )
    rendered = json.dumps(
        {"stage": list(stage), "background_column": args.background_column, "results": results},
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
