"""Clear hidden RGB from fully transparent exported texture pixels."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image


def sanitize_texture(
    path: Path,
    clear_texture_names: set[str],
    remove_bright_neutral_names: set[str],
) -> tuple[int, bool, int]:
    """Sanitize one texture and optionally clear a known-invalid sparse page."""
    image = Image.open(path).convert("RGBA")
    pixels = np.array(image)
    if path.name in clear_texture_names:
        pixels[:, :, :] = 0
        Image.fromarray(pixels, "RGBA").save(path, optimize=True)
        return 0, True, 0
    removed_bright_neutral = 0
    if path.name in remove_bright_neutral_names:
        rgb = pixels[:, :, :3].astype(np.int16)
        maximum = rgb.max(axis=2)
        minimum = rgb.min(axis=2)
        # Mugi's hair atlas contains narrow skin/white matte remnants along
        # segmentation borders. Hair highlights are warmer and more saturated;
        # remove only bright, nearly neutral pixels from the explicitly named page.
        matte = (
            (pixels[:, :, 3] > 0)
            & (maximum >= 190)
            & ((maximum - minimum) <= 55)
        )
        removed_bright_neutral = int(matte.sum())
        pixels[matte, :] = 0
    transparent = pixels[:, :, 3] == 0
    changed = transparent & np.any(pixels[:, :, :3] != 0, axis=2)
    pixels[transparent, :3] = 0
    Image.fromarray(pixels, "RGBA").save(path, optimize=True)
    return int(changed.sum()), False, removed_bright_neutral


def main() -> int:
    """Sanitize every PNG below the supplied SDK export directories."""
    parser = argparse.ArgumentParser()
    parser.add_argument("directories", nargs="+", type=Path)
    parser.add_argument(
        "--clear-texture-name",
        action="append",
        default=[],
        help="Clear an explicitly identified invalid texture page (repeatable).",
    )
    parser.add_argument(
        "--remove-bright-neutral-texture-name",
        action="append",
        default=[],
        help="Remove bright neutral matte remnants from an identified hair page.",
    )
    args = parser.parse_args()
    clear_texture_names = set(args.clear_texture_name)
    remove_bright_neutral_names = set(args.remove_bright_neutral_texture_name)
    for directory in args.directories:
        for path in sorted(directory.rglob("*.png")):
            cleared, page_cleared, matte_removed = sanitize_texture(
                path,
                clear_texture_names,
                remove_bright_neutral_names,
            )
            print(
                f"{path}: cleared_rgb={cleared} cleared_page={page_cleared} "
                f"matte_removed={matte_removed}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
