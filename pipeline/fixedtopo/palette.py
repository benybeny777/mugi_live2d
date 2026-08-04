"""Colour families used to tell skin, hair, irises and line art apart.

The topology contract fixes *where* parts belong; the palette describes *what*
they look like for one input illustration. Keeping the two apart means a new
character needs a new palette, not a new contract.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from pipeline.fixedtopo.imaging import Mask, hsv, in_hue

PALETTE_SCHEMA = "mugi-live2d/palette@1"


@dataclass(frozen=True, slots=True)
class Family:
    """One colour family expressed as an HSV window."""

    hue: tuple[float, float]
    saturation: tuple[float, float]
    value: tuple[float, float]

    def widened(self, hue: float, saturation: float, value: float) -> Family:
        """Return the same family with each window grown by the given slack."""
        return Family(
            hue=(self.hue[0] - hue, self.hue[1] + hue),
            saturation=(
                max(0.0, self.saturation[0] - saturation),
                min(1.0, self.saturation[1] + saturation),
            ),
            value=(max(0.0, self.value[0] - value), min(1.0, self.value[1] + value)),
        )


@dataclass(frozen=True, slots=True)
class Palette:
    """A named set of colour families."""

    id: str
    families: dict[str, Family]

    @staticmethod
    def load(path: Path) -> Palette:
        """Read a palette JSON document."""
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if data.get("schema") != PALETTE_SCHEMA:
            raise ValueError(f"unsupported palette schema: {data.get('schema')!r}")
        families = {
            name: Family(
                hue=tuple(entry["hue"]),
                saturation=tuple(entry["saturation"]),
                value=tuple(entry["value"]),
            )
            for name, entry in data["families"].items()
        }
        return Palette(id=data["id"], families=families)

    def widened(self, hue: float, saturation: float, value: float) -> Palette:
        """Return the palette with every family relaxed by the same slack."""
        return Palette(
            id=self.id,
            families={
                name: item.widened(hue, saturation, value) for name, item in self.families.items()
            },
        )


class ColourIndex:
    """Pre-computed HSV planes plus per-family membership for one image."""

    def __init__(self, rgba: NDArray[np.uint8], palette: Palette, alpha_threshold: int) -> None:
        """Classify every pixel of ``rgba`` into the palette's families."""
        self.rgba = rgba
        self.alpha = rgba[..., 3] >= alpha_threshold
        self.hue, self.saturation, self.value = hsv(rgba[..., :3])
        self._families = {
            name: self._select(family) & self.alpha for name, family in palette.families.items()
        }

    @property
    def shape(self) -> tuple[int, int]:
        """Return the ``(height, width)`` of the indexed image."""
        return self.alpha.shape

    def family(self, name: str) -> Mask:
        """Return the membership mask of one colour family."""
        return self._families[name]

    def _select(self, family: Family) -> Mask:
        """Return the pixels inside one HSV window."""
        low, high = family.hue
        span = high - low
        if span >= 360.0:
            hue_ok = np.ones(self.hue.shape, dtype=bool)
        else:
            hue_ok = in_hue(self.hue, low % 360.0, high % 360.0)
        return (
            hue_ok
            & (self.saturation >= family.saturation[0])
            & (self.saturation <= family.saturation[1])
            & (self.value >= family.value[0])
            & (self.value <= family.value[1])
        )
