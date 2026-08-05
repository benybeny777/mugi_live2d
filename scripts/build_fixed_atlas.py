"""Build a Mugi texture atlas on an immutable Hiyori-grade MOC topology.

The browser prototype proved the mapping.  This module is the deterministic
CLI implementation: it consumes a local topology manifest extracted from a
reference MOC and full-canvas semantic PNG plates exported from the PSD.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageChops, ImageDraw

FITTED_PARTS = {
    "PartBrow",
    "PartNose",
    "PartFace",
    "PartEar",
    "PartNeck",
    "PartBody",
    "PartArmA",
}
HAIR_PARTS = {"PartHairBack", "PartHairSide", "PartHairFront"}
REFERENCE_PARTS = {"PartCheek", "PartEyeBall", "PartEye", "PartMouth"}
LOWER_BODY_GROUPS = (
    {"ArtMesh69", "ArtMesh70", "ArtMesh74"},
    {"ArtMesh71", "ArtMesh72", "ArtMesh73"},
)

Box = tuple[float, float, float, float]
Point = tuple[float, float]


def _bounds(points: list[Point]) -> Box:
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return min(xs), min(ys), max(xs), max(ys)


def _alpha_bounds(image: Image.Image, crop: Box) -> Box | None:
    x0, y0, x1, y1 = (round(value) for value in crop)
    local = (
        image.getchannel("A")
        .crop((x0, y0, x1, y1))
        .point(lambda value: 255 if value > 8 else 0)
    )
    box = local.getbbox()
    if box is None:
        return None
    return box[0] + x0, box[1] + y0, box[2] + x0, box[3] + y0


def _fit(point: Point, source: Box, target: Box) -> Point:
    tx = max(1e-9, target[2] - target[0])
    ty = max(1e-9, target[3] - target[1])
    return (
        source[0] + (point[0] - target[0]) * (source[2] - source[0]) / tx,
        source[1] + (point[1] - target[1]) * (source[3] - source[1]) / ty,
    )


def _inverse_affine(source: list[Point], target: list[Point], origin: Point) -> tuple[float, ...]:
    target_matrix = np.asarray([[x, y, 1.0] for x, y in target], dtype=np.float64)
    source_matrix = np.asarray(source, dtype=np.float64)
    coefficients = np.linalg.solve(target_matrix, source_matrix)
    x0, y0 = origin
    return (
        float(coefficients[0, 0]),
        float(coefficients[1, 0]),
        float(coefficients[2, 0] + coefficients[0, 0] * x0 + coefficients[1, 0] * y0),
        float(coefficients[0, 1]),
        float(coefficients[1, 1]),
        float(coefficients[2, 1] + coefficients[0, 1] * x0 + coefficients[1, 1] * y0),
    )


def _paint_triangle(
    atlas: Image.Image,
    source_image: Image.Image,
    source: list[Point],
    target: list[Point],
    *,
    clear_target: bool = True,
) -> bool:
    determinant = (
        source[0][0] * (source[1][1] - source[2][1])
        + source[1][0] * (source[2][1] - source[0][1])
        + source[2][0] * (source[0][1] - source[1][1])
    )
    if abs(determinant) < 1e-8:
        return False
    x0 = max(0, math.floor(min(point[0] for point in target)))
    y0 = max(0, math.floor(min(point[1] for point in target)))
    x1 = min(atlas.width, math.ceil(max(point[0] for point in target)) + 1)
    y1 = min(atlas.height, math.ceil(max(point[1] for point in target)) + 1)
    if x1 <= x0 or y1 <= y0:
        return False
    try:
        affine = _inverse_affine(source, target, (x0, y0))
    except np.linalg.LinAlgError:
        return False
    warped = source_image.transform(
        (x1 - x0, y1 - y0),
        Image.Transform.AFFINE,
        affine,
        resample=Image.Resampling.BICUBIC,
    )
    polygon = [(round(x - x0), round(y - y0)) for x, y in target]
    mask = Image.new("L", warped.size)
    ImageDraw.Draw(mask).polygon(polygon, fill=255)
    warped.putalpha(ImageChops.multiply(warped.getchannel("A"), mask))
    # Semantic plates are sparse by design.  Clearing a hair UV island before
    # compositing turns every transparent gap in a bob-hair plate into a hole
    # in Hiyori's larger authored mesh.  Hair therefore overlays the immutable
    # reference texture; opaque Mugi pixels win while uncovered pixels retain
    # the seam-free reference fill and its deformation-safe silhouette.
    if clear_target:
        atlas.paste((0, 0, 0, 0), (x0, y0, x1, y1), mask)
    atlas.alpha_composite(warped, (x0, y0))
    return True


def build(
    topology_path: Path,
    parts_manifest_path: Path,
    reference_texture_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    topology = json.loads(topology_path.read_text(encoding="utf-8"))
    manifest = json.loads(parts_manifest_path.read_text(encoding="utf-8"))
    canvas = topology["canvas"]
    if [canvas["width"], canvas["height"]] != [
        manifest["canvas"]["width"],
        manifest["canvas"]["height"],
    ]:
        raise ValueError("topology and PSD-part manifests use different canvases")

    base = parts_manifest_path.parent
    images = {
        part_id: Image.open(base / item["file"]).convert("RGBA")
        for part_id, item in manifest["parts"].items()
    }
    atlas = Image.open(reference_texture_path).convert("RGBA")
    atlas_size = atlas.width
    if atlas.width != atlas.height:
        raise ValueError("reference texture must be square")

    def model_points(drawable: dict[str, Any]) -> list[Point]:
        positions = drawable["positions"]
        return [
            (
                canvas["originX"] + positions[index] * canvas["pixelsPerUnit"],
                canvas["originY"] - positions[index + 1] * canvas["pixelsPerUnit"],
            )
            for index in range(0, len(positions), 2)
        ]

    drawable_points = {drawable["id"]: model_points(drawable) for drawable in topology["drawables"]}
    part_points: dict[str, list[Point]] = {}
    for drawable in topology["drawables"]:
        part_points.setdefault(drawable["parentPartId"], []).extend(drawable_points[drawable["id"]])
    part_bounds = {name: _bounds(points) for name, points in part_points.items()}

    lower_groups: list[tuple[set[str], Box | None, Box]] = []
    hair_item = manifest["parts"].get("PartHairBack")
    if hair_item and hair_item.get("bbox") and "PartHairBack" in part_bounds:
        hair_source = tuple(hair_item["bbox"])
        hair_target = part_bounds["PartHairBack"]
        hair_dx = (hair_source[0] + hair_source[2] - hair_target[0] - hair_target[2]) * 0.5
        hair_dy = hair_source[1] - hair_target[1]
    else:
        hair_dx = hair_dy = 0.0

    body_item = manifest["parts"].get("PartBody")
    if body_item and body_item.get("bbox") and "PartBody" in images:
        body_source = tuple(body_item["bbox"])
        lower_start = body_source[1] + (body_source[3] - body_source[1]) * 0.46
        midpoint = manifest["canvas"]["width"] * 0.5
        horizontal_groups = ((0, midpoint), (midpoint, canvas["width"]))
        for ids, horizontal in zip(LOWER_BODY_GROUPS, horizontal_groups, strict=True):
            present_ids = ids & drawable_points.keys()
            if not present_ids:
                continue
            source_box = _alpha_bounds(
                images["PartBody"],
                (horizontal[0], lower_start, horizontal[1], canvas["height"]),
            )
            target_box = _bounds(
                [point for name in present_ids for point in drawable_points[name]]
            )
            lower_groups.append((present_ids, source_box, target_box))

    triangles = 0
    skipped_drawables = 0
    for drawable in topology["drawables"]:
        part_id = drawable["parentPartId"]
        if part_id in REFERENCE_PARTS:
            skipped_drawables += 1
            continue
        item = manifest["parts"].get(part_id)
        if not item or not item.get("bbox") or part_id not in images:
            skipped_drawables += 1
            continue
        source_box = tuple(item["bbox"])
        target_box = part_bounds[part_id]
        points = drawable_points[drawable["id"]]
        lower = next((group for group in lower_groups if drawable["id"] in group[0]), None)

        def source_point(point: Point) -> Point:
            if lower is not None and lower[1] is not None:
                return _fit(point, lower[1], lower[2])
            if part_id in FITTED_PARTS:
                return _fit(point, source_box, target_box)
            if part_id in HAIR_PARTS:
                return point[0] + hair_dx, point[1] + hair_dy
            return point

        uvs = drawable["uvs"]
        indices = drawable["indices"]
        for offset in range(0, len(indices) - 2, 3):
            vertex_ids = indices[offset : offset + 3]
            source_triangle = [source_point(points[index]) for index in vertex_ids]
            target_triangle = [
                (uvs[index * 2] * atlas_size, (1.0 - uvs[index * 2 + 1]) * atlas_size)
                for index in vertex_ids
            ]
            if _paint_triangle(
                atlas,
                images[part_id],
                source_triangle,
                target_triangle,
                clear_target=part_id not in HAIR_PARTS,
            ):
                triangles += 1
                if triangles % 250 == 0:
                    print(f"projected {triangles} triangles", flush=True)

    pixels = np.asarray(atlas).copy()
    blue = pixels[:, :, 2]
    green = pixels[:, :, 1]
    red = pixels[:, :, 0]
    iris = (blue > 70) & (blue > red * 1.15) & (blue > green * 1.08)
    pixels[:, :, 0][iris] = np.round(red[iris] * 0.55).astype(np.uint8)
    pixels[:, :, 1][iris] = np.minimum(255, np.round(blue[iris] * 0.9 + green[iris] * 0.35)).astype(
        np.uint8
    )
    pixels[:, :, 2][iris] = np.round(green[iris] * 0.7).astype(np.uint8)
    atlas = Image.fromarray(pixels, "RGBA")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    atlas.save(output_path, optimize=True)
    return {
        "schema": "mugi-live2d/fixed-atlas-report@1",
        "topology": str(topology_path.as_posix()),
        "parts": str(parts_manifest_path.as_posix()),
        "output": str(output_path.as_posix()),
        "triangles": triangles,
        "skipped_drawables": skipped_drawables,
        "drawable_count": len(topology["drawables"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--topology", type=Path, required=True)
    parser.add_argument("--parts", type=Path, required=True)
    parser.add_argument("--reference-texture", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = build(args.topology, args.parts, args.reference_texture, args.output)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
