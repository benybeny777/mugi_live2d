"""Clear hidden RGB from fully transparent exported texture pixels."""

from __future__ import annotations

import argparse
import json
import math
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt


def parse_atlas_layout(path: Path) -> dict[str, tuple[int, int, int, int]]:
    """Read the deterministic tab-separated atlas rectangle dump."""
    regions: dict[str, tuple[int, int, int, int]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("name="):
            continue
        values = dict(field.split("=", 1) for field in line.split("\t"))
        regions[values["name"]] = tuple(int(values[key]) for key in ("x", "y", "w", "h"))
    return regions


def regions_from_moc_topology(
    path: Path,
    texture_size: tuple[int, int],
    parent_parts: set[str],
    drawable_ids: set[str] | None = None,
) -> dict[str, tuple[int, int, int, int]]:
    """Convert selected drawable UV bounds to top-left-origin atlas rectangles.

    Cubism stores UV ``v`` with the origin at the bottom, while PNG rows start
    at the top.  Keeping each drawable in its own tight rectangle prevents a
    dilation from crossing into a neighbouring packed island and muddying hair
    decorations.
    """
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("schema") != "mugi-live2d/moc-topology@1":
        raise ValueError("unsupported MOC topology schema")
    texture_width, texture_height = texture_size
    if texture_width < 1 or texture_height < 1:
        raise ValueError("texture dimensions must be positive")
    drawable_ids = drawable_ids or set()
    regions: dict[str, tuple[int, int, int, int]] = {}
    for drawable in document.get("drawables", []):
        identifier = str(drawable.get("id", ""))
        if drawable.get("parentPartId") not in parent_parts and identifier not in drawable_ids:
            continue
        uvs = drawable.get("uvs", [])
        if len(uvs) < 2 or len(uvs) % 2:
            raise ValueError(f"drawable {drawable.get('id')!r} has invalid UV coordinates")
        us = [float(value) for value in uvs[0::2]]
        vs = [float(value) for value in uvs[1::2]]
        if not all(math.isfinite(value) and 0.0 <= value <= 1.0 for value in (*us, *vs)):
            raise ValueError(f"drawable {drawable.get('id')!r} has out-of-range UV coordinates")
        left = max(0, math.floor(min(us) * texture_width))
        right = min(texture_width, math.ceil(max(us) * texture_width))
        top = max(0, math.floor((1.0 - max(vs)) * texture_height))
        bottom = min(texture_height, math.ceil((1.0 - min(vs)) * texture_height))
        if right <= left or bottom <= top:
            raise ValueError(f"drawable {drawable.get('id')!r} has an empty UV rectangle")
        if not identifier or identifier in regions:
            raise ValueError(f"drawable id is missing or duplicated: {identifier!r}")
        regions[identifier] = (left, top, right - left, bottom - top)
    if not regions:
        selected = ", ".join(sorted(parent_parts | drawable_ids))
        raise ValueError(f"MOC topology contains no selected drawables: {selected}")
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


def fill_solid_rect(
    path: Path, rect: tuple[int, int, int, int], colour: tuple[int, int, int]
) -> int:
    """Paint an explicitly reserved atlas rectangle with one opaque colour."""
    image = Image.open(path).convert("RGBA")
    pixels = np.array(image)
    x, y, width, height = rect
    if x < 0 or y < 0 or x + width > image.width or y + height > image.height:
        raise ValueError("solid rectangle is outside the texture")
    pixels[y : y + height, x : x + width, :3] = colour
    pixels[y : y + height, x : x + width, 3] = 255
    Image.fromarray(pixels, "RGBA").save(path, optimize=True)
    return width * height


def dilate_region_alpha(
    path: Path,
    regions: dict[str, tuple[int, int, int, int]],
    names: set[str],
    radius: int,
) -> int:
    """Grow each opaque edge outwards by ``radius`` pixels inside named islands.

    Closing seams by filling every enclosed transparent pixel also closes the
    gaps that give the braid and the hairclip their shape, so those decorations
    turn into a solid blob. Growing only outwards from existing edges closes the
    thin seams between adjacent meshes while leaving wider intentional gaps open,
    which measurably keeps the decorations intact.
    """
    if radius < 1:
        raise ValueError("dilation radius must be at least 1")
    image = Image.open(path).convert("RGBA")
    pixels = np.array(image)
    grown = 0
    for name in names:
        if name not in regions:
            raise ValueError(f"atlas layout does not contain {name!r}")
        x, y, width, height = regions[name]
        region = pixels[y : y + height, x : x + width]
        opaque = region[:, :, 3] > 0
        if not opaque.any():
            raise ValueError(f"atlas region {name!r} has no opaque source pixels")
        # Nearest opaque source for every pixel, so grown pixels copy a real
        # neighbouring colour instead of a single flat average.
        distance, (rows, columns) = distance_transform_edt(~opaque, return_indices=True)
        added = (~opaque) & (distance <= radius)
        region[added, :3] = region[rows[added], columns[added], :3]
        region[added, 3] = 255
        grown += int(added.sum())
    Image.fromarray(pixels, "RGBA").save(path, optimize=True)
    return grown


def fill_hair_cap_regions(
    path: Path,
    regions: dict[str, tuple[int, int, int, int]],
    names: set[str],
) -> int:
    """Fill the enclosed interior of a ring-shaped back-hair texture.

    The face ArtMesh is rendered above the back hair, so the back-hair plate
    must be a continuous cap behind it. Cutting a face-shaped hole here makes
    the canvas visible when independently deforming hair moves at its boundary.
    """
    image = Image.open(path).convert("RGBA")
    pixels = np.array(image)
    changed = 0
    for name in names:
        if name not in regions:
            raise ValueError(f"atlas layout does not contain {name!r}")
        x, y, width, height = regions[name]
        region = pixels[y : y + height, x : x + width]
        opaque = region[:, :, 3] > 0
        if not opaque.any():
            raise ValueError(f"atlas region {name!r} has no opaque source pixels")
        colour = np.median(region[:, :, :3][opaque], axis=0).astype(np.uint8)
        barrier = opaque.copy()
        # Close the ring at its lowest row that still has opaque boundaries on
        # both sides. A fixed percentage is brittle across characters whose
        # bob/long-hair proportions differ.
        cutoff = height - 1
        for candidate in range(cutoff, -1, -1):
            occupied = np.flatnonzero(opaque[candidate])
            if occupied.size >= 2 and occupied[-1] - occupied[0] >= width * 0.4:
                cutoff = candidate
                break
        nearby = opaque[max(0, cutoff - 2) : min(height, cutoff + 3)].any(axis=0)
        occupied_x = np.flatnonzero(nearby)
        if occupied_x.size < 2:
            raise ValueError(f"atlas region {name!r} has no hair-ring boundary")
        barrier[cutoff, occupied_x[0] : occupied_x[-1] + 1] = True
        outside = np.zeros((height, width), dtype=bool)
        queue: deque[tuple[int, int]] = deque()
        for column in range(width):
            for row in (0, height - 1):
                if not barrier[row, column] and not outside[row, column]:
                    outside[row, column] = True
                    queue.append((row, column))
        for row in range(height):
            for column in (0, width - 1):
                if not barrier[row, column] and not outside[row, column]:
                    outside[row, column] = True
                    queue.append((row, column))
        while queue:
            row, column = queue.popleft()
            for next_row, next_column in (
                (row - 1, column),
                (row + 1, column),
                (row, column - 1),
                (row, column + 1),
            ):
                if (
                    0 <= next_row < height
                    and 0 <= next_column < width
                    and not barrier[next_row, next_column]
                    and not outside[next_row, next_column]
                ):
                    outside[next_row, next_column] = True
                    queue.append((next_row, next_column))
        cap = ~barrier & ~outside
        cap[cutoff:, :] = False
        region[cap, :3] = colour
        region[cap, 3] = 255
        changed += int(cap.sum())
    Image.fromarray(pixels, "RGBA").save(path, optimize=True)
    return changed


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
    parser.add_argument("--moc-topology", type=Path)
    parser.add_argument(
        "--dilate-parent-part",
        action="append",
        default=[],
        help="Dilate every drawable UV island belonging to this Cubism parent part.",
    )
    parser.add_argument(
        "--dilate-drawable",
        action="append",
        default=[],
        help="Dilate one exact drawable UV island (repeatable).",
    )
    parser.add_argument(
        "--remove-bright-neutral-region-name",
        action="append",
        default=[],
        help="Remove matte pixels only inside this named atlas rectangle (repeatable).",
    )
    parser.add_argument("--fill-hair-cap-region-name", action="append", default=[])
    parser.add_argument("--dilate-region-name", action="append", default=[])
    parser.add_argument("--dilate-radius", type=int, default=32)
    parser.add_argument("--fill-solid-rect", help="x,y,width,height,RRGGBB")
    args = parser.parse_args()
    clear_texture_names = set(args.clear_texture_name)
    remove_bright_neutral_names = set(args.remove_bright_neutral_texture_name)
    region_names = set(args.remove_bright_neutral_region_name)
    hair_cap_names = set(args.fill_hair_cap_region_name)
    dilate_names = set(args.dilate_region_name)
    regions = parse_atlas_layout(args.atlas_layout) if args.atlas_layout else {}
    topology_parts = set(args.dilate_parent_part)
    topology_drawables = set(args.dilate_drawable)
    if args.moc_topology and not (topology_parts or topology_drawables):
        parser.error("--moc-topology requires --dilate-parent-part or --dilate-drawable")
    if (topology_parts or topology_drawables) and not args.moc_topology:
        parser.error("topology-based dilation requires --moc-topology")
    if (region_names or hair_cap_names or dilate_names) and not regions:
        parser.error("--atlas-layout is required for region operations")
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
            if hair_cap_names and path.name == "texture_00.png":
                cap_filled = fill_hair_cap_regions(path, regions, hair_cap_names)
                print(f"{path}: region_hair_cap_filled={cap_filled}")
            if dilate_names and path.name == "texture_00.png":
                grown = dilate_region_alpha(path, regions, dilate_names, args.dilate_radius)
                print(f"{path}: region_dilated={grown} radius={args.dilate_radius}")
            if (topology_parts or topology_drawables) and path.name == "texture_00.png":
                with Image.open(path) as topology_texture:
                    texture_size = topology_texture.size
                topology_regions = regions_from_moc_topology(
                    args.moc_topology,
                    texture_size,
                    topology_parts,
                    topology_drawables,
                )
                grown = dilate_region_alpha(
                    path,
                    topology_regions,
                    set(topology_regions),
                    args.dilate_radius,
                )
                print(
                    f"{path}: topology_islands_dilated={len(topology_regions)} "
                    f"pixels_grown={grown} radius={args.dilate_radius}"
                )
            if args.fill_solid_rect and path.name == "texture_00.png":
                fields = args.fill_solid_rect.split(",")
                if len(fields) != 5:
                    parser.error("--fill-solid-rect requires x,y,width,height,RRGGBB")
                rect = tuple(int(value) for value in fields[:4])
                hex_colour = fields[4].removeprefix("#")
                if len(hex_colour) != 6:
                    parser.error("solid rectangle colour must be RRGGBB")
                colour = tuple(int(hex_colour[index : index + 2], 16) for index in (0, 2, 4))
                solid_filled = fill_solid_rect(path, rect, colour)
                print(f"{path}: solid_rect_filled={solid_filled}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
