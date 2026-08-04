"""Build a Photoshop sandbox: a small crop plus the masks that bound the work.

Photoshop's generative fill paints wherever the active selection allows, so the
whole safety of this step comes from handing over a crop whose editable area is
already the only place a change is wanted. Everything else in the crop is
recorded as locked and is checked again when the result comes back.

There are two shapes of work here and the manifest names which one it is. An
``extend`` sandbox grows a silhouette outward by a ring. An ``underlay``
sandbox completes a shape the fixed-topology contract already pins, on a layer
beneath the artwork, which is what the face needs: its forehead is missing
under the bangs and no ring around the existing edge can reach it.
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
from pipeline.sandbox.region import Region

#: Alpha at or above this counts as solid artwork that must survive untouched.
LOCK_ALPHA = 250

#: Depth into the artwork at which its flat base colour is read. Mugi's face
#: layer carries a shaded rim about 20 px deep, so a shallower sample returns
#: that rim instead of the skin an underlay has to match.
BASE_DEPTH = 16.0

#: How a sandbox is meant to be filled, which decides what the colour check
#: compares against.
#:
#: ``extend`` grows an existing silhouette outward by a ring, so every new
#: pixel continues the artwork it touches.
#: ``underlay`` completes a fixed shape that the artwork only partly covers,
#: on a layer beneath it, so every new pixel is the layer's flat base colour.
EXTEND = "extend"
UNDERLAY = "underlay"

#: Instructions repeated into every manifest so the GUI side never has to guess.
RULES: tuple[str, ...] = (
    "Open base.png only. Never run generative fill on the master PSD.",
    "Open editable.png too, then in base.png use Select > Load Selection with "
    "editable.png as the source document.",
    "Keep that selection active for the whole generation.",
    "Do not resize, rotate, crop, or change the canvas size of base.png.",
    "Leave every pixel under locked.png byte-identical.",
    "Generate flat base colour continuous with the surrounding art: no fabric, "
    "weave, cloth, knit, pattern, texture, gradient banding, or lighting detail.",
    "Export the result as the return file named in this manifest: PNG, "
    "transparency on, 100% scale, same pixel size as base.png. Flattening on "
    "export is expected; do not overwrite base.png.",
)

#: Added when the sandbox completes a fixed shape rather than growing an edge.
UNDERLAY_RULES: tuple[str, ...] = (
    "This sandbox is an underlay: the selection is the part of {region} the "
    "layer does not cover yet, plus the seam it needs to meet the artwork.",
    "Paint it flat {colour} on a new layer *below* the existing artwork, then "
    "flatten on export. Do not repaint the artwork on top.",
    "One colour only. No outline, no rim shading, no gradient, no highlight: "
    "the drawn edge already exists on the layer above.",
    "The selection is the whole permitted area. Do not enlarge the shape to "
    "'look right' - a shape larger than the selection is rejected.",
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


def base_colour(rgba: NDArray[np.uint8]) -> tuple[int, int, int] | None:
    """Return the layer's flat base colour, or ``None`` when it has no artwork.

    Read at ``BASE_DEPTH`` inside the artwork so the drawn edge is left out. On
    Mugi's face that is the difference between the skin an underlay must match
    and the hair-toned rim the artist painted over it.
    """
    solid = rgba[..., 3] >= LOCK_ALPHA
    if not solid.any():
        return None
    interior = imaging.erode(solid, BASE_DEPTH)
    sample = interior if interior.any() else solid
    median = np.median(rgba[sample][:, :3], axis=0)
    return int(median[0]), int(median[1]), int(median[2])


def regions(
    rgba: NDArray[np.uint8],
    grow: float,
    seam: float,
    region: Region | None,
) -> tuple[Mask, Mask, Mask]:
    """Return ``(present, locked, editable)`` masks for a canvas-sized layer.

    ``present`` is the artwork that exists today, ``locked`` is the part of it
    that must come back unchanged, and ``editable`` is where new pixels may
    appear. The ``seam`` ring keeps the existing anti-aliased edge out of the
    locked set so a clean blend is not a failure.

    Without a ``region`` the editable area is a ring of ``grow`` pixels around
    the whole silhouette: the shape only ever moves outward, by that much.
    With one it is the part of that fixed shape the artwork does not cover,
    plus the ``grow`` pixels of that gap which fall outside the shape. That
    second ring is what lets an underlay meet a silhouette drawn slightly proud
    of the shape, and it is deliberately not a ring around the whole layer:
    edges that are already complete stay where the artist put them.
    """
    alpha = rgba[..., 3]
    present = alpha > 0
    locked = imaging.erode(alpha >= LOCK_ALPHA, seam)
    empty = np.zeros_like(present)

    if region is None:
        missing = empty
        seamed = imaging.dilate(present, grow) & ~present if grow > 0 else empty
    else:
        inside = region.mask(present.shape)
        missing = inside & ~present
        seamed = imaging.dilate(missing, grow) & ~inside & ~present if grow > 0 else empty
    return present, locked, (missing | seamed) & ~present & ~locked


def sandbox_box(present: Mask, editable: Mask, margin: int, canvas: tuple[int, int]) -> Box:
    """Return the crop handed to Photoshop: the work plus a margin of context."""
    covered = imaging.bbox(present | editable)
    if covered is None:
        raise ValueError("the layer is empty and has no editable region")
    x0, y0, x1, y1 = covered
    return _clip((x0 - margin, y0 - margin, x1 + margin, y1 + margin), canvas)


def _rules(region: Region | None, colour: tuple[int, int, int] | None) -> tuple[str, ...]:
    """Return the instructions that belong on this sandbox."""
    if region is None:
        return RULES
    swatch = "#{:02X}{:02X}{:02X}".format(*colour) if colour else "the layer's base colour"
    filled = tuple(rule.format(region=region.name, colour=swatch) for rule in UNDERLAY_RULES)
    return RULES + filled


def write_sandbox(
    rgba: NDArray[np.uint8],
    source: dict,
    out: Path,
    name: str,
    grow: float = 24.0,
    seam: float = 2.0,
    margin: int = 32,
    region: Region | None = None,
) -> mf.Manifest:
    """Write the sandbox files and manifest for one canvas-sized layer raster."""
    canvas = (int(rgba.shape[1]), int(rgba.shape[0]))
    present, locked, editable = regions(rgba, grow, seam, region)
    if not editable.any():
        raise ValueError("nothing to generate: --grow is 0 and the region is already covered")

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
    colour = base_colour(_crop(rgba, box))
    sandbox = {
        "box": list(box),
        "size": [box[2] - box[0], box[3] - box[1]],
        "origin": [box[0], box[1]],
        "grow": grow,
        "seam": seam,
        "margin": margin,
        "fill_mode": EXTEND if region is None else UNDERLAY,
        # Recorded in sandbox pixels: the GUI side never sees canvas coordinates.
        "region": region.shifted(-box[0], -box[1]).to_json() if region else None,
        "base_colour": list(colour) if colour else None,
        "editable_pixels": int(_crop(editable, box).sum()),
        "locked_pixels": int(_crop(locked, box).sum()),
    }
    ret = {
        "file": "filled.png",
        "size": sandbox["size"],
        "mode": "RGBA",
        "paste_origin": [box[0], box[1]],
    }

    document = mf.build(name, source, sandbox, files, ret, _rules(region, colour))
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
    region: Region | None = None,
) -> dict:
    """Read one PSD layer and hand it to :func:`write_sandbox`."""
    rgba, _ = psdlayer.extract_from_file(psd, layer)
    source = {
        "psd": str(psd).replace("\\", "/"),
        "psd_sha256": mf.sha256_file(psd),
        "layer": layer,
    }
    name = identifier or layer.strip(psdlayer.PATH_SEPARATOR).replace(psdlayer.PATH_SEPARATOR, "-")
    return write_sandbox(rgba, source, out, name, grow, seam, margin, region).raw
