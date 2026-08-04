"""Synthetic layers and returned images used by the sandbox tests.

The fabric helper reproduces the shape of the failure that made this pipeline
necessary: a generative fill that returned a woven cloth texture where flat
skin was expected.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray
from PIL import Image

from pipeline.fixedtopo import imaging
from pipeline.sandbox import region as regions

CANVAS = (200, 200)
SKIN = (243, 214, 199)
HAIR = (108, 82, 66)
STONE = (150, 146, 140)

#: The fixed shape a face layer is expected to fill, in fixture pixels.
FACE_OVAL = (60, 40, 140, 160)

#: Depth of the drawn rim the artist painted over the skin, in pixels. Mugi's
#: face layer carries one about this deep relative to its size, and it is the
#: reason an underlay borders hair tone on every side.
RIM_DEPTH = 10.0


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


def shaded_disc(canvas: tuple[int, int] = CANVAS, radius: int = 40) -> NDArray[np.uint8]:
    """Return a disc whose upper part is hair-toned and lower part is skin.

    Mugi's face layer looks like this: the See-through split left dark
    hair-coloured pixels along the top edge, so a single reference colour for
    the layer would be wrong everywhere.
    """
    rgba = disc(canvas, radius)
    top = np.arange(canvas[1])[:, None] < canvas[1] / 2
    rgba[..., :3] = np.where(top[..., None], np.array(HAIR, dtype=np.uint8), rgba[..., :3])
    return rgba


def oval_region(box: tuple[int, int, int, int] = FACE_OVAL) -> regions.Region:
    """Return the fixed shape the underlay fixtures complete."""
    return regions.Region("face_oval", "ellipse", box, "tests.sandbox_fixtures")


def capped_oval(
    canvas: tuple[int, int] = CANVAS,
    oval: tuple[int, int, int, int] = FACE_OVAL,
    cap: float = 0.35,
    rim: float = RIM_DEPTH,
) -> NDArray[np.uint8]:
    """Return a layer shaped like Mugi's face: a fixed oval with its top missing.

    The artist painted a hair-toned rim over the skin, so every edge of what
    exists is dark. The top ``cap`` of the oval is not covered at all, which is
    the forehead the bangs hide and no ring around the existing silhouette can
    reach.
    """
    raster = (canvas[1], canvas[0])
    inside = imaging.ellipse_mask(raster, oval)
    _, y0, _, y1 = oval
    covered = np.zeros(raster, dtype=bool)
    covered[int(y0 + (y1 - y0) * cap) :, :] = True
    present = inside & covered

    rgba = np.zeros(raster + (4,), dtype=np.uint8)
    rgba[..., :3] = np.array(SKIN, dtype=np.uint8)
    drawn_edge = present & ~imaging.erode(present, rim)
    rgba[..., :3] = np.where(drawn_edge[..., None], np.array(HAIR, dtype=np.uint8), rgba[..., :3])
    rgba[..., 3] = np.where(present, 255, 0)
    return rgba


def underlay_mask(
    base: NDArray[np.uint8],
    oval: tuple[int, int, int, int] = FACE_OVAL,
    grow: int = 0,
) -> NDArray[np.bool_]:
    """Return the pixels an ellipse painted *under* the layer would show through.

    ``grow`` enlarges the ellipse past the shape it was given, which is what
    the 2026-08-04 Photoshop return did.
    """
    x0, y0, x1, y1 = oval
    shape = imaging.ellipse_mask(base.shape[:2], (x0 - grow, y0 - grow, x1 + grow, y1 + grow))
    return shape & (base[..., 3] == 0)


def underlay(
    base: NDArray[np.uint8],
    oval: tuple[int, int, int, int] = FACE_OVAL,
    colour=SKIN,
    grow: int = 0,
) -> NDArray[np.uint8]:
    """Return ``base`` flattened over a flat ellipse painted beneath it."""
    return fill(base, underlay_mask(base, oval, grow), colour)


def extend(base: NDArray[np.uint8], region: NDArray[np.bool_]) -> NDArray[np.uint8]:
    """Return ``base`` with ``region`` carrying the nearest existing colour.

    This is what a correct completion looks like on shaded artwork: the colour
    each new pixel borders, carried outward, with no invented detail.
    """
    from pipeline.sandbox.qa import nearest_colour

    out = base.copy()
    nearest = nearest_colour(base, base[..., 3] >= 250)
    out[..., :3] = np.where(region[..., None], nearest, out[..., :3])
    out[..., 3] = np.where(region, 255, out[..., 3])
    return out


def fabric(
    base: NDArray[np.uint8],
    region: NDArray[np.bool_],
    colour=None,
    period: int = 6,
    amplitude: float = 18.0,
) -> NDArray[np.uint8]:
    """Return ``base`` with ``region`` painted a woven cloth pattern.

    The average colour is left correct on purpose: a weave passes a colour
    check and has to be caught by the texture and pattern measures instead.
    """
    out = extend(base, region) if colour is None else fill(base, region, colour)
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


def load_rgba(path) -> NDArray[np.uint8]:
    """Read a PNG back as an RGBA array."""
    with Image.open(path) as opened:
        return np.asarray(opened.convert("RGBA"), dtype=np.uint8)


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
