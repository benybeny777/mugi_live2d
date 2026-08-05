"""Clear hidden RGB from fully transparent exported texture pixels."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image


def parse_atlas_layout(path: Path) -> dict[str, tuple[int, int, int, int]]:
    """Read the deterministic tab-separated atlas rectangle dump."""
    regions: dict[str, tuple[int, int, int, int]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("name="):
            continue
        values = dict(field.split("=", 1) for field in line.split("\t"))
        regions[values["name"]] = tuple(int(values[key]) for key in ("x", "y", "w", "h"))
    return regions


def remove_bright_neutral_regions(
    path: Path,
    regions: dict[str, tuple[int, int, int, int]],
    names: set[str],
) -> int:
    """Remove segmentation matte only inside explicitly named UV islands."""
    image = Image.open(path).convert("RGBA")
    pixels = np.array(image)
    removed = 0
    for name in names:
        if name not in regions:
            raise ValueError(f"atlas layout does not contain {name!r}")
        x, y, width, height = regions[name]
        region = pixels[y : y + height, x : x + width]
        rgb = region[:, :, :3].astype(np.int16)
        maximum = rgb.max(axis=2)
        minimum = rgb.min(axis=2)
        matte = (
            (region[:, :, 3] > 0)
            & (maximum >= 190)
            & ((maximum - minimum) <= 55)
        )
        removed += int(matte.sum())
        region[matte, :] = 0
    Image.fromarray(pixels, "RGBA").save(path, optimize=True)
    return removed


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
    parser.add_argument("--atlas-layout", type=Path)
    parser.add_argument(
        "--remove-bright-neutral-region-name",
        action="append",
        default=[],
        help="Remove matte pixels only inside this named atlas rectangle (repeatable).",
    )
    args = parser.parse_args()
    clear_texture_names = set(args.clear_texture_name)
    remove_bright_neutral_names = set(args.remove_bright_neutral_texture_name)
    region_names = set(args.remove_bright_neutral_region_name)
    regions = parse_atlas_layout(args.atlas_layout) if args.atlas_layout else {}
    if region_names and not regions:
        parser.error("--atlas-layout is required with --remove-bright-neutral-region-name")
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
            if region_names and path.name == "texture_00.png":
                region_removed = remove_bright_neutral_regions(path, regions, region_names)
                print(f"{path}: region_matte_removed={region_removed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
