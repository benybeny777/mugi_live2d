"""The fixed-topology contract: what the master rig expects, in canvas pixels.

A contract is data, not code. It pins the canvas, the anchor landmarks the rig
was built around, an envelope for every layer, and the checks a candidate must
survive. Changing a threshold here changes what "pass" means, so the file is
reviewed like source and never edited to make a run go green.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pipeline.fixedtopo import imaging
from pipeline.fixedtopo.imaging import Box, Mask

CONTRACT_SCHEMA = "mugi-live2d/fixed-topology@2"

Point = tuple[float, float]


@dataclass(frozen=True, slots=True)
class Region:
    """Where one layer is allowed to live on the canvas."""

    name: str
    shape: str
    box: Box

    def mask(self, canvas: tuple[int, int]) -> Mask:
        """Rasterise the envelope for a ``(width, height)`` canvas."""
        raster = (canvas[1], canvas[0])
        if self.shape == "ellipse":
            return imaging.ellipse_mask(raster, self.box)
        if self.shape == "box":
            return imaging.box_mask(raster, self.box)
        raise ValueError(f"unknown region shape: {self.shape!r}")

    @property
    def size(self) -> tuple[int, int]:
        """Return the envelope's width and height."""
        return self.box[2] - self.box[0], self.box[3] - self.box[1]


@dataclass(frozen=True, slots=True)
class Contract:
    """A parsed fixed-topology contract."""

    id: str
    canvas: tuple[int, int]
    anchors: dict[str, Point]
    regions: dict[str, Region]
    required_layers: tuple[str, ...]
    optional_layers: tuple[str, ...]
    draw_order: tuple[str, ...]
    clipping: dict[str, str]
    minimum_bbox: dict[str, dict[str, int]]
    minimum_pixels: dict[str, int]
    containment: tuple[dict[str, Any], ...]
    overlap: tuple[dict[str, Any], ...]
    seams: tuple[dict[str, Any], ...]
    envelopes: dict[str, dict[str, float]]
    islands: dict[str, dict[str, int]]
    proportions: dict[str, float]
    raw: dict[str, Any] = field(repr=False, default_factory=dict)

    @property
    def all_layers(self) -> tuple[str, ...]:
        """Return required and optional layer names in contract order."""
        return self.required_layers + self.optional_layers

    def region(self, name: str) -> Region | None:
        """Return one layer's envelope, or ``None`` when it is unconstrained."""
        return self.regions.get(name)

    def envelope_rule(self, name: str) -> dict[str, float]:
        """Return the envelope tolerances that apply to one layer."""
        rule = dict(self.envelopes.get("default", {}))
        rule.update(self.envelopes.get(name, {}))
        return rule

    def island_rule(self, name: str) -> dict[str, int]:
        """Return the stray-fragment limits that apply to one layer."""
        rule = dict(self.islands.get("default", {}))
        rule.update(self.islands.get(name, {}))
        return rule

    def anchor_pair(self, names: tuple[str, ...]) -> list[Point]:
        """Return the listed anchors in order."""
        return [self.anchors[name] for name in names]


def load(path: Path | str) -> Contract:
    """Read and validate a contract document."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    schema = data.get("schema")
    if schema != CONTRACT_SCHEMA:
        raise ValueError(f"unsupported contract schema: {schema!r}; expected {CONTRACT_SCHEMA!r}")

    regions = {
        name: Region(name=name, shape=entry.get("shape", "box"), box=tuple(entry["box"]))
        for name, entry in data.get("regions", {}).items()
    }
    required = tuple(data["required_layers"])
    optional = tuple(data.get("optional_layers", ()))
    draw_order = tuple(data.get("draw_order", ())) or required + optional

    missing = [name for name in required + optional if name not in draw_order]
    if missing:
        raise ValueError("draw_order is missing layers: " + ", ".join(missing))
    unknown = [name for name in regions if name not in required + optional]
    if unknown:
        raise ValueError("regions reference unknown layers: " + ", ".join(sorted(unknown)))

    return Contract(
        id=data["id"],
        canvas=(data["canvas"]["width"], data["canvas"]["height"]),
        anchors={name: tuple(point) for name, point in data.get("anchors", {}).items()},
        regions=regions,
        required_layers=required,
        optional_layers=optional,
        draw_order=draw_order,
        clipping=dict(data.get("clipping", {})),
        minimum_bbox=dict(data.get("minimum_bbox", {})),
        minimum_pixels=dict(data.get("minimum_pixels", {})),
        containment=tuple(data.get("containment", ())),
        overlap=tuple(data.get("overlap", ())),
        seams=tuple(data.get("seams", ())),
        envelopes=dict(data.get("envelopes", {})),
        islands=dict(data.get("islands", {})),
        proportions=dict(data.get("proportions", {})),
        raw=data,
    )
