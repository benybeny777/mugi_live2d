"""Put an approved sandbox result back at its place on the master canvas.

The result is written as a standalone canvas-sized transparent PNG, never into
the PSD. Re-importing that PNG as a layer is a Cubism/Photoshop step and stays
with the GUI side, so nothing here can damage the master document.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray
from PIL import Image

from pipeline.fixedtopo import imaging
from pipeline.sandbox import manifest as mf
from pipeline.sandbox import psdlayer
from pipeline.sandbox import qa as checks


def read_layer(source: Path, layer: str) -> tuple[NDArray[np.uint8], tuple[int, int]]:
    """Return the untouched layer as canvas-sized RGBA.

    ``source`` is normally the master PSD. A canvas-sized PNG written earlier
    by ``extract`` is also accepted, so a second import does not have to parse
    the whole document again.
    """
    if source.suffix.lower() == ".psd":
        return psdlayer.extract_from_file(source, layer)
    with Image.open(source) as opened:
        rgba = np.asarray(opened.convert("RGBA"), dtype=np.uint8)
    return rgba, (int(rgba.shape[1]), int(rgba.shape[0]))


def paste(canvas_rgba: NDArray[np.uint8], patch: NDArray[np.uint8], origin: tuple[int, int]):
    """Return a copy of the canvas with ``patch`` written at ``origin``."""
    out = canvas_rgba.copy()
    x, y = origin
    out[y : y + patch.shape[0], x : x + patch.shape[1]] = patch
    return out


def restore(
    directory: Path,
    filled: Path,
    out: Path,
    reviewed_by: str | None,
    psd: Path | None = None,
) -> dict[str, Any]:
    """Verify a returned image and, once signed off, write the completed canvas PNG.

    ``reviewed_by`` is deliberately required. Every automated check can pass on
    an image a person would reject at a glance, so the pipeline stops at
    ``review_required`` until a name is attached to the decision.
    """
    manifest = mf.load(directory / "manifest.json")
    report = checks.evaluate(manifest, directory, filled)

    if report["failed"]:
        report["written"] = None
        return report
    if not reviewed_by:
        report["written"] = None
        report["hint"] = "checks passed; rerun with --reviewed-by NAME to write the canvas PNG"
        return report

    source = Path(psd) if psd else Path(manifest.source["psd"])
    layer_rgba, canvas = read_layer(source, manifest.source["layer"])
    if list(canvas) != list(manifest.canvas):
        raise ValueError(f"canvas is {canvas}, manifest expects {tuple(manifest.canvas)}")
    digest = mf.sha256_file(source)
    if digest != manifest.source["psd_sha256"]:
        raise ValueError(
            f"{source} changed since export (sha256 {digest[:12]}…); rerun export before import"
        )

    with Image.open(filled) as opened:
        patch = np.asarray(opened.convert("RGBA"), dtype=np.uint8)
    completed = paste(layer_rgba, patch, tuple(manifest.ret["paste_origin"]))

    out.parent.mkdir(parents=True, exist_ok=True)
    imaging.save_rgba(completed, out)

    report["status"] = "approved"
    report["reviewed_by"] = reviewed_by
    report["written"] = str(out).replace("\\", "/")
    report["written_sha256"] = mf.sha256_file(out)
    report["written_alpha_bbox"] = list(imaging.bbox(completed[..., 3] > 0) or ())
    return report
