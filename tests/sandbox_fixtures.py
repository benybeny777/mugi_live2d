"""Synthetic layers and returned images used by the sandbox tests.

The fabric helper reproduces the shape of the failure that made this pipeline
necessary: a generative fill that returned a woven cloth texture where flat
skin was expected.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray
from PIL import Image

CANVAS = (200, 200)
SKIN = (243, 214, 199)


def disc(canvas: tuple[int, int] = CANVAS, radius: int = 40, colour=SKIN) -> NDArray[np.uint8]:
    """Return a canvas-sized RGBA layer holding one solid disc."""
    width, height = canvas
    ys = np.arange(height)[:, None] - height / 2.0
    xs = np.arange(width)[None, :] - width / 2.0
    inside = (ys**2 + xs**2) <= radius**2
    rgba = np.zeros((height, width, 4), dtype=np.uint8)
    rgba[..., :3] = np.array(colour, dtype=np.uint8)
    rgba[..., 3] = np.where(inside, 255, 0)
    return rgba


def fill(base: NDArray[np.uint8], region: NDArray[np.bool_], colour=SKIN) -> NDArray[np.uint8]:
    """Return ``base`` with ``region`` painted a flat colour, as a good fill would."""
    out = base.copy()
    out[..., :3] = np.where(region[..., None], np.array(colour, dtype=np.uint8), out[..., :3])
    out[..., 3] = np.where(region, 255, out[..., 3])
    return out


def fabric(
    base: NDArray[np.uint8],
    region: NDArray[np.bool_],
    colour=SKIN,
    period: int = 6,
    amplitude: float = 18.0,
) -> NDArray[np.uint8]:
    """Return ``base`` with ``region`` painted a woven cloth pattern.

    The mean colour is left alone on purpose: a weave passes a colour check and
    has to be caught by the texture and pattern measures instead.
    """
    out = fill(base, region, colour)
    height, width = region.shape
    ys = np.arange(height)[:, None]
    xs = np.arange(width)[None, :]
    weave = np.sin(2 * np.pi * xs / period) * np.cos(2 * np.pi * ys / period)
    shaded = np.clip(out[..., :3].astype(np.float32) + amplitude * weave[..., None], 0, 255)
    out[..., :3] = np.where(region[..., None], shaded.astype(np.uint8), out[..., :3])
    return out


def save(rgba: NDArray[np.uint8], path) -> None:
    """Write an RGBA array as a PNG."""
    Image.fromarray(rgba, mode="RGBA").save(path, optimize=True)


def load_mask(path) -> NDArray[np.bool_]:
    """Read an 8-bit mask PNG back as a boolean array."""
    with Image.open(path) as opened:
        return np.asarray(opened.convert("L"), dtype=np.uint8) > 127


def source(name: str = "synthetic") -> dict:
    """Return the ``source`` block used for a sandbox that has no PSD behind it."""
    return {"psd": f"{name}.psd", "psd_sha256": "0" * 64, "layer": f"/test/{name}"}


class FakeMask:
    """A layer mask with just the bounds that ``describe`` reports."""

    def __init__(self, offset, size):
        self.bbox = (offset[0], offset[1], offset[0] + size[0], offset[1] + size[1])


class FakeLayer:
    """The slice of the psd-tools layer API that :mod:`pipeline.sandbox.psdlayer` uses."""

    def __init__(self, name, colour, shape=None, mask=None, offset=(0, 0), opacity=255):
        self.name = name
        self.offset = offset
        self.opacity = opacity
        self.visible = True
        self.blend_mode = "BlendMode.NORMAL"
        self.size = (0, 0) if colour is None else (colour.shape[1], colour.shape[0])
        self.mask = None if mask is None else FakeMask(offset, self.size)
        self._planes = {"color": colour, "shape": shape, "mask": mask}

    def is_group(self) -> bool:
        """Pixel layers are never groups."""
        return False

    def numpy(self, channel: str | None = None, real_mask: bool = True):
        """Return one float plane, or ``None`` when the layer has none."""
        return self._planes.get(channel)


class FakeGroup(list):
    """A group of fake layers, iterable like a psd-tools group."""

    def __init__(self, name, children):
        super().__init__(children)
        self.name = name

    def is_group(self) -> bool:
        """Groups are groups."""
        return True
