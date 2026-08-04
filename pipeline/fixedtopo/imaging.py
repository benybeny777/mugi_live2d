"""Deterministic raster helpers shared by the fixed-topology pipeline.

Every operation here is pure and order-independent so that two runs with the
same inputs and settings produce byte-identical masks. Radius based morphology
uses an exact Euclidean distance transform instead of iterated structuring
elements, which keeps results stable regardless of SciPy's iteration order.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray
from PIL import Image
from scipy import ndimage

Mask = NDArray[np.bool_]
Box = tuple[int, int, int, int]

#: 4-neighbour structure. Diagonal-only bridges are treated as separate parts so
#: a hairline of anti-aliasing cannot merge two components into one.
CONNECTIVITY = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]], dtype=bool)


def load_rgba(path) -> NDArray[np.uint8]:
    """Read an image as an ``H x W x 4`` uint8 array."""
    with Image.open(path) as opened:
        return np.asarray(opened.convert("RGBA"), dtype=np.uint8)


def save_rgba(array: NDArray[np.uint8], path) -> None:
    """Write an ``H x W x 4`` uint8 array as a PNG."""
    Image.fromarray(array, mode="RGBA").save(path, optimize=True)


def hsv(
    rgb: NDArray[np.uint8],
) -> tuple[NDArray[np.float32], NDArray[np.float32], NDArray[np.float32]]:
    """Split an RGB array into hue (0-360), saturation and value (both 0-1)."""
    scaled = rgb.astype(np.float32) / 255.0
    red, green, blue = scaled[..., 0], scaled[..., 1], scaled[..., 2]
    value = scaled.max(axis=-1)
    minimum = scaled.min(axis=-1)
    chroma = value - minimum
    saturation = np.where(value > 0, chroma / np.maximum(value, 1e-6), 0.0)

    safe = np.maximum(chroma, 1e-6)
    hue = np.where(
        value == red,
        ((green - blue) / safe) % 6.0,
        np.where(value == green, (blue - red) / safe + 2.0, (red - green) / safe + 4.0),
    )
    hue = np.where(chroma <= 1e-6, 0.0, hue * 60.0)
    return hue.astype(np.float32), saturation.astype(np.float32), value.astype(np.float32)


def in_hue(hue: NDArray[np.float32], low: float, high: float) -> Mask:
    """Return where a hue falls inside a range that may wrap past 360 degrees."""
    if low <= high:
        return (hue >= low) & (hue <= high)
    return (hue >= low) | (hue <= high)


def _grow(mask: Mask, radius: float) -> Mask:
    """Grow without any border handling."""
    return ndimage.distance_transform_edt(~mask) <= radius


def _shrink(mask: Mask, radius: float) -> Mask:
    """Shrink without any border handling."""
    return ndimage.distance_transform_edt(mask) > radius


def _padded(mask: Mask, radius: float, mode: str) -> tuple[Mask, int]:
    """Return a padded copy plus the pad width, so borders behave predictably."""
    pad = int(np.ceil(radius)) + 1
    if mode == "edge":
        return np.pad(mask, pad, mode="edge"), pad
    return np.pad(mask, pad, mode="constant", constant_values=False), pad


def dilate(mask: Mask, radius: float) -> Mask:
    """Grow a mask by an exact Euclidean radius."""
    if radius <= 0 or not mask.any():
        return mask.copy()
    return _grow(mask, radius)


def erode(mask: Mask, radius: float) -> Mask:
    """Shrink a mask by an exact Euclidean radius.

    Everything outside the canvas counts as background, so a part that runs off
    the edge is eroded there too instead of being silently held in place.
    """
    if radius <= 0 or not mask.any():
        return mask.copy()
    padded, pad = _padded(mask, radius, "constant")
    return _shrink(padded, radius)[pad:-pad, pad:-pad]


def close(mask: Mask, radius: float) -> Mask:
    """Fill gaps narrower than ``radius`` without moving the outer boundary.

    The canvas edge is replicated first, otherwise the erosion half of the
    operation would shave content that legitimately runs off the canvas.
    """
    if radius <= 0 or not mask.any():
        return mask.copy()
    padded, pad = _padded(mask, radius, "edge")
    return _shrink(_grow(padded, radius), radius)[pad:-pad, pad:-pad]


def open_(mask: Mask, radius: float) -> Mask:
    """Drop protrusions thinner than ``radius``."""
    if radius <= 0 or not mask.any():
        return mask.copy()
    padded, pad = _padded(mask, radius, "edge")
    return _grow(_shrink(padded, radius), radius)[pad:-pad, pad:-pad]


def fill_holes(mask: Mask) -> Mask:
    """Close every background region fully enclosed by the mask."""
    return ndimage.binary_fill_holes(mask, structure=CONNECTIVITY)


def label(mask: Mask) -> tuple[NDArray[np.int32], NDArray[np.int64]]:
    """Return connected component labels and each component's pixel count."""
    labels, count = ndimage.label(mask, structure=CONNECTIVITY)
    if count == 0:
        return labels.astype(np.int32), np.zeros(0, dtype=np.int64)
    sizes = np.bincount(labels.ravel(), minlength=count + 1)[1:]
    return labels.astype(np.int32), sizes.astype(np.int64)


def largest_component(mask: Mask) -> Mask:
    """Keep only the biggest connected component."""
    labels, sizes = label(mask)
    if sizes.size == 0:
        return mask.copy()
    return labels == int(np.argmax(sizes)) + 1


def remove_small(mask: Mask, min_area: int) -> Mask:
    """Drop connected components below ``min_area`` pixels."""
    if min_area <= 1:
        return mask.copy()
    labels, sizes = label(mask)
    if sizes.size == 0:
        return mask.copy()
    keep = np.concatenate(([False], sizes >= min_area))
    return keep[labels]


def island_sizes(mask: Mask) -> NDArray[np.int64]:
    """Return component pixel counts sorted from largest to smallest."""
    _, sizes = label(mask)
    return np.sort(sizes)[::-1]


def bbox(mask: Mask) -> Box | None:
    """Return the tight ``(x0, y0, x1, y1)`` bounds, exclusive on the far edge."""
    if not mask.any():
        return None
    rows = np.flatnonzero(mask.any(axis=1))
    columns = np.flatnonzero(mask.any(axis=0))
    return int(columns[0]), int(rows[0]), int(columns[-1]) + 1, int(rows[-1]) + 1


def centroid(mask: Mask) -> tuple[float, float] | None:
    """Return the ``(x, y)`` centre of mass, or ``None`` for an empty mask."""
    if not mask.any():
        return None
    rows, columns = np.nonzero(mask)
    return float(columns.mean()), float(rows.mean())


def box_mask(shape: tuple[int, int], box: Box) -> Mask:
    """Rasterise an axis-aligned box, clipped to the canvas."""
    height, width = shape
    x0, y0, x1, y1 = box
    mask = np.zeros(shape, dtype=bool)
    mask[max(0, y0) : min(height, y1), max(0, x0) : min(width, x1)] = True
    return mask


def ellipse_mask(shape: tuple[int, int], box: Box) -> Mask:
    """Rasterise an axis-aligned ellipse inscribed in ``box``."""
    height, width = shape
    x0, y0, x1, y1 = box
    center_x, center_y = (x0 + x1 - 1) / 2.0, (y0 + y1 - 1) / 2.0
    radius_x, radius_y = max((x1 - x0 - 1) / 2.0, 0.5), max((y1 - y0 - 1) / 2.0, 0.5)
    ys = (np.arange(height, dtype=np.float32) - center_y) / radius_y
    xs = (np.arange(width, dtype=np.float32) - center_x) / radius_x
    return (ys[:, None] ** 2 + xs[None, :] ** 2) <= 1.0


def apply_mask(rgba: NDArray[np.uint8], mask: Mask) -> NDArray[np.uint8]:
    """Return a copy of ``rgba`` whose alpha is cleared outside ``mask``."""
    out = rgba.copy()
    out[..., 3] = np.where(mask, out[..., 3], 0)
    return out


def flood_from_border(mask: Mask) -> Mask:
    """Return the part of ``mask`` reachable from the canvas border."""
    if not mask.any():
        return mask.copy()
    labels, _ = label(mask)
    border = np.concatenate((labels[0], labels[-1], labels[:, 0], labels[:, -1]))
    outside = np.unique(border[border > 0])
    return np.isin(labels, outside)
