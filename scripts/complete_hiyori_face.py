"""Rebuild Hiyori-compatible Mugi face layers deterministically.

The generic See-through exporter intentionally leaves some compatibility
layers empty.  Hiyori's real topology, however, owns the sclera, iris and lash
segments independently.  This module reconstructs those pixels from Mugi's
original illustration using fixed, documented regions and colour/geometry
rules.  It can repair an existing layered PSD or post-process freshly built
full-canvas PNG layers.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from psd_tools import PSDImage
from psd_tools.api.layers import PixelLayer

CREATOR_REPOSITORY = Path(r"C:\00_PG\30_live")
MODEL_REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CREATOR_REPOSITORY))

from app.core.parts import PART_DISPLAY_NAMES_JA, PartName  # noqa: E402


@dataclass(frozen=True, slots=True)
class EyeSpec:
    side: str
    roi: tuple[int, int, int, int]
    center: tuple[float, float]
    radii: tuple[float, float]
    white: PartName
    iris: PartName
    highlight: PartName
    combined_lash: PartName
    lash_segments: tuple[PartName, ...]
    lash_x_boundaries: tuple[int, ...]


EYES = (
    EyeSpec(
        "left",
        (1278, 536, 1447, 711),
        (1365.0, 625.0),
        (77.0, 72.0),
        PartName.EYE_WHITE_LEFT,
        PartName.EYE_IRIS_LEFT,
        PartName.EYE_HIGHLIGHT_LEFT,
        PartName.EYELASH_LEFT,
        (
            PartName.EYELASH_LEFT_1,
            PartName.EYELASH_LEFT_2,
            PartName.EYELASH_LEFT_3,
            PartName.EYELASH_LEFT_4,
            PartName.EYELASH_LEFT_5,
            PartName.EYELASH_LEFT_6,
        ),
        (1288, 1314, 1326, 1361, 1397, 1416, 1436),
    ),
    EyeSpec(
        "right",
        (1518, 536, 1693, 711),
        (1608.0, 625.0),
        (79.0, 72.0),
        PartName.EYE_WHITE_RIGHT,
        PartName.EYE_IRIS_RIGHT,
        PartName.EYE_HIGHLIGHT_RIGHT,
        PartName.EYELASH_RIGHT,
        (
            PartName.EYELASH_RIGHT_1,
            PartName.EYELASH_RIGHT_2,
            PartName.EYELASH_RIGHT_3,
            PartName.EYELASH_RIGHT_4,
            PartName.EYELASH_RIGHT_5,
            PartName.EYELASH_RIGHT_6,
            PartName.EYELASH_RIGHT_7,
        ),
        (1520, 1547, 1562, 1593, 1625, 1642, 1659, 1684),
    ),
)

MOUTH_ROI = (1438, 718, 1532, 786)


def _canvas_from_mask(source: Image.Image, mask: np.ndarray) -> Image.Image:
    rgba = np.asarray(source, dtype=np.uint8).copy()
    rgba[:, :, 3] = np.where(mask, rgba[:, :, 3], 0).astype(np.uint8)
    rgba[rgba[:, :, 3] == 0, :3] = 0
    return Image.fromarray(rgba, mode="RGBA")


def _paste_local_mask(
    size: tuple[int, int], roi: tuple[int, int, int, int], local: np.ndarray
) -> np.ndarray:
    mask = np.zeros((size[1], size[0]), dtype=bool)
    x0, y0, x1, y1 = roi
    mask[y0:y1, x0:x1] = local
    return mask


def _eye_masks(
    source: Image.Image, spec: EyeSpec, existing: Image.Image | None = None
) -> dict[PartName, np.ndarray]:
    x0, y0, x1, y1 = spec.roi
    eye_source = source if existing is None else existing
    rgba = np.asarray(eye_source.crop(spec.roi), dtype=np.uint8)
    rgb = rgba[:, :, :3].astype(np.int16)
    yy, xx = np.mgrid[y0:y1, x0:x1]
    nx = (xx - spec.center[0]) / spec.radii[0]
    ny = (yy - spec.center[1]) / spec.radii[1]
    radius = nx * nx + ny * ny
    opaque = rgba[:, :, 3] > 8
    maximum = rgb.max(axis=2)
    minimum = rgb.min(axis=2)
    chroma = maximum - minimum
    luminance = rgb.mean(axis=2)

    # Skin is warm (large red/blue difference); sclera is bright and neutral.
    iris_shape = ((xx - spec.center[0]) / 56.0) ** 2 + ((yy - spec.center[1]) / 72.0) ** 2 <= 1.0
    if existing is None:
        white = (
            opaque
            & (radius <= 1.08)
            & (yy >= spec.center[1] - spec.radii[1] * 0.56)
            & (rgb[:, :, 0] > 232)
            & (rgb[:, :, 1] > 228)
            & (rgb[:, :, 2] > 211)
            & (chroma < 27)
            & ~iris_shape
        )
    else:
        white = opaque & ~iris_shape & (luminance > 150) & (chroma / np.maximum(maximum, 1) < 0.24)
    saturation = chroma / np.maximum(maximum, 1)
    green_region = opaque if existing is not None else iris_shape
    green = (
        green_region
        & opaque
        & (rgb[:, :, 1] > rgb[:, :, 0] * 1.03)
        & (rgb[:, :, 1] > rgb[:, :, 2] * 1.02)
        & (saturation > 0.13)
    )
    green_neighbourhood = (
        np.asarray(
            Image.fromarray(np.where(green, 255, 0).astype(np.uint8), mode="L").filter(
                ImageFilter.MaxFilter(11)
            )
        )
        > 0
    )
    dark_iris = (
        iris_shape & green_neighbourhood & opaque & (luminance < 105) & (yy >= spec.center[1] - 58)
    )
    iris = (opaque & green_neighbourhood) if existing is not None else (green | dark_iris)
    if existing is not None:
        white = opaque & ~iris & (radius <= 1.25) & (yy >= spec.center[1] - spec.radii[1] * 0.78)
    iris_neighbourhood = (
        np.asarray(
            Image.fromarray(np.where(iris, 255, 0).astype(np.uint8), mode="L").filter(
                ImageFilter.MaxFilter(13)
            )
        )
        > 0
    )
    highlight = iris_shape & iris_neighbourhood & opaque & (luminance > 212) & (chroma < 38)

    # Keep only the eye-outline annulus.  This rejects the pupil and the bangs
    # while preserving both upper and lower painted lash strokes.
    dark_outline = (
        opaque
        & (luminance < (135 if existing is not None else 78))
        & (rgb[:, :, 1] <= rgb[:, :, 0] * 1.25 + 3)
        & (radius >= 0.55)
        & (radius <= 1.18)
        & (yy >= spec.center[1] - spec.radii[1] * 0.88)
        & (yy <= spec.center[1] + spec.radii[1] * 0.88)
    )
    if existing is None:
        lash = dark_outline
    else:
        upper_lid = (
            opaque
            & (radius <= 1.18)
            & (yy >= spec.center[1] - spec.radii[1] * 0.92)
            & (yy <= spec.center[1] - 16)
        )
        lash = dark_outline | upper_lid
    # A one-pixel fringe prevents interpolation holes between the lash pieces.
    lash_image = Image.fromarray(np.where(lash, 255, 0).astype(np.uint8), mode="L")
    lash = np.asarray(lash_image.filter(ImageFilter.MaxFilter(3))) > 0

    result = {
        spec.white: _paste_local_mask(source.size, spec.roi, white),
        spec.iris: _paste_local_mask(source.size, spec.roi, iris),
        spec.highlight: _paste_local_mask(source.size, spec.roi, highlight),
        # Hiyori uses segmented meshes; this compatibility layer stays empty
        # to avoid drawing the outline twice.
        spec.combined_lash: np.zeros((source.height, source.width), dtype=bool),
    }
    lash_y, lash_x = np.nonzero(lash)
    if len(lash_x) < len(spec.lash_segments) * 8:
        raise ValueError(f"{spec.side} eyelash extraction is unexpectedly sparse")
    for index, name in enumerate(spec.lash_segments):
        left = spec.lash_x_boundaries[index] - x0 - 4
        right = spec.lash_x_boundaries[index + 1] - x0 + 4
        local = lash & (np.indices(lash.shape)[1] >= left) & (np.indices(lash.shape)[1] < right)
        result[name] = _paste_local_mask(source.size, spec.roi, local)
    return result


def _mouth_layers(source: Image.Image) -> dict[PartName, Image.Image]:
    x0, y0, x1, y1 = MOUTH_ROI
    rgba = np.asarray(source.crop(MOUTH_ROI), dtype=np.uint8)
    rgb = rgba[:, :, :3].astype(np.int16)
    luminance = rgb.mean(axis=2)
    yy, xx = np.mgrid[y0:y1, x0:x1]
    # The neutral smile is a small brown stroke.  Restrict extraction to the
    # central lower-face band so skin shading cannot become part of the mouth.
    painted = (
        (rgba[:, :, 3] > 8)
        & (luminance < 205)
        & (xx >= 1450)
        & (xx <= 1520)
        & (yy >= 741)
        & (yy <= 772)
    )
    py, px = np.nonzero(painted)
    if len(px) < 8:
        raise ValueError("mouth extraction is unexpectedly sparse")
    center_y = float(np.median(py))
    upper = painted & (np.mgrid[: painted.shape[0], : painted.shape[1]][0] <= center_y)
    lower = painted & ~upper
    # If the antialiased source stroke falls on one row, deterministically give
    # alternating pixels to both deformable edges.
    if not lower.any():
        coords = np.column_stack(np.nonzero(upper))
        lower = np.zeros_like(upper)
        lower[coords[1::2, 0], coords[1::2, 1]] = True
        upper[coords[1::2, 0], coords[1::2, 1]] = False

    def global_mask(local: np.ndarray) -> np.ndarray:
        return _paste_local_mask(source.size, MOUTH_ROI, local)

    source_upper = _canvas_from_mask(source, global_mask(upper))
    source_lower = _canvas_from_mask(source, global_mask(lower))
    lip_mask = np.zeros_like(painted)
    distance = np.abs(px - ((x0 + x1) / 2 - x0))
    lip_selection = np.argsort(distance, kind="stable")[: max(8, len(px) // 12)]
    lip_mask[py[lip_selection], px[lip_selection]] = True
    lip = _canvas_from_mask(source, global_mask(lip_mask))

    # Closed-state inner/highlight artwork is hidden by Cubism opacity, but it
    # must have real texture area for ParamMouthOpenY to reveal and deform.
    inner = Image.new("RGBA", source.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(inner)
    draw.ellipse((1456, 746, 1514, 772), fill=(105, 43, 52, 255))
    draw.ellipse((1467, 758, 1503, 772), fill=(205, 92, 104, 255))
    highlight = Image.new("RGBA", source.size, (0, 0, 0, 0))
    ImageDraw.Draw(highlight).arc(
        (1468, 757, 1503, 769), 8, 172, fill=(255, 194, 199, 230), width=3
    )
    return {
        PartName.MOUTH: lip,
        PartName.MOUTH_UPPER: source_upper,
        PartName.MOUTH_LOWER: source_lower,
        PartName.MOUTH_INNER: inner,
        PartName.MOUTH_HIGHLIGHT: highlight,
    }


def complete_face_layers(source_path: Path, layers_directory: Path) -> dict[str, object]:
    """Replace face-component PNGs and return quantitative evidence."""
    with Image.open(source_path) as opened:
        source = opened.convert("RGBA")
    replacements: dict[PartName, Image.Image] = {}
    for spec in EYES:
        existing_path = layers_directory / f"{spec.iris.value}.png"
        existing = None
        if existing_path.exists():
            with Image.open(existing_path) as opened:
                candidate = opened.convert("RGBA")
            if candidate.size == source.size and candidate.getchannel("A").getbbox():
                existing = candidate
        paint_source = source if existing is None else existing
        eye_replacements = {
            name: _canvas_from_mask(paint_source, mask)
            for name, mask in _eye_masks(source, spec, existing).items()
        }
        # Preserve high-quality parts already produced by See-through.  Only
        # empty compatibility pieces are reconstructed.
        for name in (spec.highlight, *spec.lash_segments):
            path = layers_directory / f"{name.value}.png"
            if not path.exists():
                continue
            with Image.open(path) as opened:
                original = opened.convert("RGBA")
            if (
                original.size == source.size
                and np.count_nonzero(np.asarray(original.getchannel("A"))) >= 8
            ):
                eye_replacements[name] = original
        for name in spec.lash_segments:
            if np.count_nonzero(np.asarray(eye_replacements[name].getchannel("A"))) < 8:
                raise ValueError(f"{spec.side} {name.value} remains sparse after preservation/fill")
        replacements.update(eye_replacements)
    replacements.update(_mouth_layers(source))
    layers_directory.mkdir(parents=True, exist_ok=True)
    evidence: dict[str, object] = {"source": str(source_path), "layers": {}}
    for name, image in replacements.items():
        path = layers_directory / f"{name.value}.png"
        image.save(path, optimize=True)
        alpha = image.getchannel("A")
        bbox = alpha.getbbox()
        evidence["layers"][name.display_name_ja] = {
            "pixels": int(np.count_nonzero(np.asarray(alpha))),
            "bbox": list(bbox) if bbox else None,
        }
    return evidence


def _leaf_layers(layers: object) -> list[object]:
    result: list[object] = []
    for layer in layers:
        if layer.is_group():
            result.extend(_leaf_layers(layer))
        else:
            result.append(layer)
    return result


def repair_psd(
    source_path: Path, psd_path: Path, destination: Path, work: Path
) -> dict[str, object]:
    """Replace only face pixels while preserving the original PSD structure."""
    psd = PSDImage.open(psd_path)
    with Image.open(source_path) as opened:
        source_size = opened.size
    if psd.size != source_size:
        raise ValueError(f"PSD/source size mismatch: {psd.size}")
    by_display = {display: name for name, display in PART_DISPLAY_NAMES_JA.items()}
    work.mkdir(parents=True, exist_ok=True)
    layers_by_name: dict[PartName, object] = {}
    for layer in _leaf_layers(psd):
        name = by_display.get(layer.name)
        if name is None:
            continue
        layers_by_name[name] = layer
        rendered = layer.composite()
        canvas = Image.new("RGBA", psd.size, (0, 0, 0, 0))
        if rendered is not None:
            canvas.alpha_composite(rendered.convert("RGBA"), (layer.left, layer.top))
        path = work / f"{name.value}.png"
        canvas.save(path, optimize=True)
    evidence = complete_face_layers(source_path, work)
    replacement_names = (
        {spec.white for spec in EYES}
        | {spec.iris for spec in EYES}
        | {spec.highlight for spec in EYES}
        | {spec.combined_lash for spec in EYES}
        | {name for spec in EYES for name in spec.lash_segments}
        | {
            PartName.MOUTH,
            PartName.MOUTH_UPPER,
            PartName.MOUTH_LOWER,
            PartName.MOUTH_INNER,
            PartName.MOUTH_HIGHLIGHT,
        }
    )
    missing = sorted(name.value for name in replacement_names - set(layers_by_name))
    if missing:
        raise ValueError(f"PSD is missing required layers: {', '.join(missing)}")
    for name in replacement_names:
        old = layers_by_name[name]
        parent = old.parent
        index = parent.index(old)
        with Image.open(work / f"{name.value}.png") as opened:
            full = opened.convert("RGBA")
        bbox = full.getchannel("A").getbbox()
        if bbox is None:
            pixels = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
            offset = (0, 0)
        else:
            pixels = full.crop(bbox)
            offset = (bbox[0], bbox[1])
        replacement = PixelLayer.frompil(
            pixels,
            parent,
            name=name.value,
            top=offset[1],
            left=offset[0],
        )
        # Keep the legacy Pascal field ASCII-compatible and store Japanese in
        # Photoshop's Unicode layer-name block, matching the main exporter.
        replacement.name = old.name
        replacement.opacity = old.opacity
        replacement.blend_mode = old.blend_mode
        parent.remove(replacement)
        parent.remove(old)
        parent.insert(index, replacement)
    destination.parent.mkdir(parents=True, exist_ok=True)
    psd.save(destination)
    evidence["input_psd"] = str(psd_path)
    evidence["output_psd"] = str(destination)
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source", type=Path, default=MODEL_REPOSITORY / "source/mugi-original.png"
    )
    parser.add_argument("--layers", type=Path)
    parser.add_argument("--input-psd", type=Path)
    parser.add_argument("--output-psd", type=Path)
    parser.add_argument("--work", type=Path, default=MODEL_REPOSITORY / "temp/hiyori-face-layers")
    args = parser.parse_args()
    if args.input_psd:
        if not args.output_psd:
            parser.error("--output-psd is required with --input-psd")
        evidence = repair_psd(args.source, args.input_psd, args.output_psd, args.work)
    elif args.layers:
        evidence = complete_face_layers(args.source, args.layers)
    else:
        parser.error("provide --layers or --input-psd")
    import json

    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
