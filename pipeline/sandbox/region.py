"""The fixed shape a sandbox fill is allowed to complete.

A generative fill needs a boundary that comes from the rig, not from whatever
rectangle looked about right on the day. The fixed-topology contract already
pins one for the face, so this module reads it back and hands it to the
exporter as a rasterisable shape.

Two frames live in that contract and they are not interchangeable. ``frame``
and ``regions`` are stated in the retargeted canvas frame, which is where the
artwork ends up *after* calibration scales it. ``calibration`` also records the
same shapes measured on the reference image, and that is the frame
``mugi-hiyori-compatible-clean.psd`` is still in. Only the second kind is
offered here, because a sandbox is cut from that PSD.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pipeline.fixedtopo import imaging
from pipeline.fixedtopo.imaging import Box, Mask

#: The contract a sandbox is bounded by unless another one is named.
DEFAULT_CONTRACT = Path("pipeline/topology.mugi-hiyori-v2.json")

#: Regions expressed in the master document's own pixel frame, as
#: ``name -> (shape, key under "calibration")``. Anything not listed here has
#: no measured shape in that frame yet, and guessing one is how the last
#: rectangle happened.
SOURCE_REGIONS: dict[str, tuple[str, str, str | None]] = {
    "face_oval": ("ellipse", "face_oval_source", None),
    "face_forehead": ("ellipse", "face_oval_source", "face_forehead_clip_source"),
}


@dataclass(frozen=True, slots=True)
class Region:
    """One fixed shape, in the pixel frame of the document it bounds."""

    name: str
    shape: str
    box: Box
    origin: str
    clip: Box | None = None

    def mask(self, raster: tuple[int, int]) -> Mask:
        """Rasterise the shape for a ``(height, width)`` array."""
        if self.shape == "ellipse":
            result = imaging.ellipse_mask(raster, self.box)
        elif self.shape == "box":
            result = imaging.box_mask(raster, self.box)
        else:
            raise ValueError(f"unknown region shape: {self.shape!r}")
        return result if self.clip is None else result & imaging.box_mask(raster, self.clip)

    def shifted(self, dx: int, dy: int) -> Region:
        """Return the same shape moved by ``(dx, dy)`` pixels."""
        x0, y0, x1, y1 = self.box
        clip = None
        if self.clip is not None:
            cx0, cy0, cx1, cy1 = self.clip
            clip = (cx0 + dx, cy0 + dy, cx1 + dx, cy1 + dy)
        return Region(
            self.name,
            self.shape,
            (x0 + dx, y0 + dy, x1 + dx, y1 + dy),
            self.origin,
            clip,
        )

    def to_json(self) -> dict[str, Any]:
        """Return the JSON form recorded in a manifest."""
        document = {
            "name": self.name,
            "shape": self.shape,
            "box": list(self.box),
            "origin": self.origin,
        }
        if self.clip is not None:
            document["clip"] = list(self.clip)
        return document


def from_json(entry: dict[str, Any] | None) -> Region | None:
    """Return the region a manifest recorded, or ``None`` when it had none."""
    if not entry:
        return None
    box = tuple(int(value) for value in entry["box"])
    clip_entry = entry.get("clip")
    clip = tuple(int(value) for value in clip_entry) if clip_entry else None
    return Region(entry["name"], entry["shape"], box, entry.get("origin", "manifest"), clip)  # type: ignore[arg-type]


def named(name: str, path: Path | str = DEFAULT_CONTRACT) -> Region:
    """Return one named region from a fixed-topology contract."""
    if name not in SOURCE_REGIONS:
        known = ", ".join(sorted(SOURCE_REGIONS)) or "none"
        raise ValueError(f"no region named {name!r} in the document frame; known regions: {known}")
    shape, key, clip_key = SOURCE_REGIONS[name]
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    calibration = document.get("calibration", {})
    if key not in calibration:
        raise ValueError(f"{path} has no calibration.{key}; rerun the fixed-topology calibration")
    box = tuple(int(value) for value in calibration[key])
    clip = None
    origin = f"{Path(path).as_posix()}#calibration.{key}"
    if clip_key is not None:
        if clip_key not in calibration:
            raise ValueError(
                f"{path} has no calibration.{clip_key}; rerun the fixed-topology calibration"
            )
        clip = tuple(int(value) for value in calibration[clip_key])
        origin += f" clipped by calibration.{clip_key}"
    return Region(name, shape, box, origin, clip)  # type: ignore[arg-type]
