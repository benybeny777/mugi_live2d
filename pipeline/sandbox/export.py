"""Build a Photoshop sandbox: a small crop plus the masks that bound the work.

Photoshop's generative fill paints wherever the active selection allows, so the
whole safety of this step comes from handing over a crop whose editable area is
already the only place a change is wanted. Everything else in the crop is
recorded as locked and is checked again when the result comes back.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from PIL import Image

from pipeline.fixedtopo import imaging
from pipeline.fixedtopo.imaging import Box, Mask
from pipeline.sandbox import manifest as mf
from pipeline.sandbox import psdlayer

#: Alpha at or above this counts as solid artwork that must survive untouched.
LOCK_ALPHA = 250

#: Instructions repeated into every manifest so the GUI side never has to guess.
RULES: tuple[str, ...] = (
    "Open base.png only. Never run generative fill on the master PSD.",
    "Load editable.png as a selection and keep the selection active while generating.",
    "Do not flatten, resize, rotate, crop, or change the canvas of base.png.",
    "Leave every pixel under locked.png byte-identical.",
    "Generate flat base colour continuous with the surrounding art: no fabric, "
    "weave, cloth, knit, pattern, texture, gradient banding, or lighting detail.",
    "Save the result as the return file listed in this manifest, as RGBA PNG, "
    "same pixel size as base.png, with transparency preserved.",
)


def _clip(box: Box, canvas: tuple[int, int]) -> Box:
    """Clamp a box to the canvas."""
    width, height = canvas
    x0, y0, x1, y1 = box
    return max(0, x0), max(0, y0), min(width, x1), min(height, y1)


def _crop(array: NDArray, box: Box) -> NDArray:
    """Return the ``(x0, y0, x1, y1)`` crop of a canvas-sized array."""
    x0, y0, x1, y1 = box
    return array[y0:y1, x0:x1]


def _save_mask(mask: Mask, path: Path) -> str:
    """Write a boolean mask as an 8-bit PNG and return its SHA-256."""
    Image.fromarray(np.where(mask, 255, 0).astype(np.uint8), mode="L").save(path, optimize=True)
    return mf.sha256_file(path)


def _save_rgba(rgba: NDArray[np.uint8], path: Path) -> str:
    """Write an RGBA array as a PNG and return its SHA-256."""
    imaging.save_rgba(rgba, path)
    return mf.sha256_file(path)


def regions(
    rgba: NDArray[np.uint8],
    grow: float,
    seam: float,
    target: Box | None,
) -> tuple[Mask, Mask, Mask]:
    """Return ``(present, locked, editable)`` masks for a canvas-sized layer.

    ``present`` is the artwork that exists today, ``locked`` is the part of it
    that must come back unchanged, and ``editable`` is where new pixels may
    appear: a ring of ``grow`` pixels around the artwork, plus any explicit
    target box, minus the locked core. The ``seam`` ring keeps the existing
    anti-aliased edge out of the locked set so a clean blend is not a failure.
    """
    alpha = rgba[..., 3]
    present = alpha > 0
    locked = imaging.erode(alpha >= LOCK_ALPHA, seam)

    editable = imaging.dilate(present, grow) & ~present if grow > 0 else np.zeros_like(present)
    if target is not None:
        editable = editable | imaging.box_mask(present.shape, target)
    return present, locked, editable & ~locked


def sandbox_box(present: Mask, editable: Mask, margin: int, canvas: tuple[int, int]) -> Box:
    """Return the crop handed to Photoshop: the work plus a margin of context."""
    covered = imaging.bbox(present | editable)
    if covered is None:
        raise ValueError("the layer is empty and has no editable region")
    x0, y0, x1, y1 = covered
    return _clip((x0 - margin, y0 - margin, x1 + margin, y1 + margin), canvas)


def write_sandbox(
    rgba: NDArray[np.uint8],
    source: dict,
    out: Path,
    name: str,
    grow: float = 24.0,
    seam: float = 2.0,
    margin: int = 32,
    target: Box | None = None,
) -> mf.Manifest:
    """Write the sandbox files and manifest for one canvas-sized layer raster."""
    canvas = (int(rgba.shape[1]), int(rgba.shape[0]))
    present, locked, editable = regions(rgba, grow, seam, target)
    if not editable.any():
        raise ValueError("nothing to generate: --grow is 0 and no --target was given")

    box = sandbox_box(present, editable, margin, canvas)
    directory = out / name
    directory.mkdir(parents=True, exist_ok=True)

    files = {
        "base": mf.FileRecord(
            "base.png", _save_rgba(_crop(rgba, box), directory / "base.png"), "input"
        ),
        "editable": mf.FileRecord(
            "editable.png",
            _save_mask(_crop(editable, box), directory / "editable.png"),
            "selection",
        ),
        "locked": mf.FileRecord(
            "locked.png",
            _save_mask(_crop(locked, box), directory / "locked.png"),
            "must-not-change",
        ),
    }

    alpha_box = imaging.bbox(present)
    source = dict(source)
    source.update(
        {
            "canvas": list(canvas),
            "layer_alpha_bbox": list(alpha_box) if alpha_box else None,
            "layer_opaque_pixels": int(present.sum()),
        }
    )
    sandbox = {
        "box": list(box),
        "size": [box[2] - box[0], box[3] - box[1]],
        "origin": [box[0], box[1]],
        "grow": grow,
        "seam": seam,
        "margin": margin,
        "target": list(target) if target else None,
        "editable_pixels": int(_crop(editable, box).sum()),
        "locked_pixels": int(_crop(locked, box).sum()),
    }
    ret = {
        "file": "filled.png",
        "size": sandbox["size"],
        "mode": "RGBA",
        "paste_origin": [box[0], box[1]],
    }

    document = mf.build(name, source, sandbox, files, ret, RULES)
    mf.dump(document, directory / "manifest.json")
    return document


def export(
    psd: Path,
    layer: str,
    out: Path,
    identifier: str | None = None,
    grow: float = 24.0,
    seam: float = 2.0,
    margin: int = 32,
    target: Box | None = None,
) -> dict:
    """Read one PSD layer and hand it to :func:`write_sandbox`."""
    rgba, _ = psdlayer.extract_from_file(psd, layer)
    source = {
        "psd": str(psd).replace("\\", "/"),
        "psd_sha256": mf.sha256_file(psd),
        "layer": layer,
    }
    name = identifier or layer.strip(psdlayer.PATH_SEPARATOR).replace(psdlayer.PATH_SEPARATOR, "-")
    return write_sandbox(rgba, source, out, name, grow, seam, margin, target).raw
