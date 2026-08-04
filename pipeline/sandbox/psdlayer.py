"""Read one PSD layer as canvas-aligned RGBA with its layer mask baked in.

``psd-tools`` returns a layer's colour, transparency and mask as separate
float32 planes. Multiplying them here, instead of calling ``composite()``,
keeps two properties the pipeline depends on: the layer's own opacity is not
applied, so hidden helper layers such as ``口中`` (opacity 0) still yield their
artwork, and the result is a plain unpremultiplied RGBA raster that Photoshop
can open without a document-wide mask.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

Canvas = tuple[int, int]
Rgba = NDArray[np.uint8]

#: Separator used in the layer paths accepted on the command line.
PATH_SEPARATOR = "/"


def open_document(path: Path):
    """Open a PSD, importing ``psd-tools`` lazily so tests stay dependency free."""
    try:
        from psd_tools import PSDImage
    except ImportError as error:  # pragma: no cover - exercised only without the extra
        raise RuntimeError(
            "psd-tools is required to read PSD files; run `uv sync` first"
        ) from error
    return PSDImage.open(path)


def walk(document) -> Iterator[tuple[str, object]]:
    """Yield ``(path, layer)`` for every pixel layer, deepest last within a group."""

    def descend(group, prefix: str) -> Iterator[tuple[str, object]]:
        for layer in group:
            path = f"{prefix}{PATH_SEPARATOR}{layer.name}"
            if layer.is_group():
                yield from descend(layer, path)
            else:
                yield path, layer

    yield from descend(document, "")


def describe(document) -> list[dict[str, object]]:
    """Summarise every pixel layer for the ``list`` command."""
    entries: list[dict[str, object]] = []
    for path, layer in walk(document):
        mask = layer.mask
        entries.append(
            {
                "path": path,
                "offset": list(layer.offset),
                "size": list(layer.size),
                "has_mask": mask is not None,
                "mask_bbox": list(mask.bbox) if mask is not None else None,
                "opacity": int(layer.opacity),
                "visible": bool(layer.visible),
                "blend_mode": str(layer.blend_mode).rsplit(".", 1)[-1],
            }
        )
    return entries


def resolve(document, wanted: str):
    """Return the single layer matching ``wanted`` as a full path or a leaf name."""
    candidates = list(walk(document))
    exact = [layer for path, layer in candidates if path == wanted]
    if len(exact) == 1:
        return exact[0]
    leaf = [pair for pair in candidates if pair[0].rsplit(PATH_SEPARATOR, 1)[-1] == wanted]
    if len(leaf) == 1:
        return leaf[0][1]
    if not leaf:
        raise KeyError(f"no layer named {wanted!r}; use `list` to see the available paths")
    listed = ", ".join(path for path, _ in leaf)
    raise KeyError(f"layer name {wanted!r} is ambiguous; use one of: {listed}")


def _place(plane: NDArray[np.float32] | None, offset, canvas: Canvas) -> NDArray[np.float32] | None:
    """Paste a layer-sized plane into a canvas-sized one, cropping what overflows."""
    if plane is None:
        return None
    width, height = canvas
    depth = plane.shape[2]
    placed = np.zeros((height, width, depth), dtype=np.float32)
    left, top = int(offset[0]), int(offset[1])
    x0, y0 = max(left, 0), max(top, 0)
    x1 = min(left + plane.shape[1], width)
    y1 = min(top + plane.shape[0], height)
    if x0 >= x1 or y0 >= y1:
        return placed
    placed[y0:y1, x0:x1] = plane[y0 - top : y1 - top, x0 - left : x1 - left]
    return placed


def _plane(layer, channel: str, canvas: Canvas) -> NDArray[np.float32] | None:
    """Return one canvas-aligned float plane, or ``None`` when the layer has none."""
    data = layer.numpy(channel)
    if data is None:
        return None
    return _place(np.asarray(data, dtype=np.float32), layer.offset, canvas)


def extract(layer, canvas: Canvas, apply_opacity: bool = False) -> Rgba:
    """Return the layer as canvas-sized RGBA with its mask baked into alpha.

    ``apply_opacity`` is off by default: layers that are parked at opacity 0 in
    the master document still hold the artwork the completion step needs.
    """
    width, height = canvas
    colour = _plane(layer, "color", canvas)
    if colour is None:
        return np.zeros((height, width, 4), dtype=np.uint8)

    alpha = np.ones((height, width, 1), dtype=np.float32)
    for channel in ("shape", "mask"):
        plane = _plane(layer, channel, canvas)
        if plane is not None:
            alpha = alpha * plane[..., :1]
    if apply_opacity:
        alpha = alpha * (float(layer.opacity) / 255.0)

    rgba = np.concatenate((colour[..., :3], alpha), axis=2)
    return np.rint(np.clip(rgba, 0.0, 1.0) * 255.0).astype(np.uint8)


def extract_from_file(psd: Path, wanted: str, apply_opacity: bool = False) -> tuple[Rgba, Canvas]:
    """Open ``psd``, extract one layer, and report the document canvas size."""
    document = open_document(psd)
    canvas = (int(document.width), int(document.height))
    return extract(resolve(document, wanted), canvas, apply_opacity), canvas
