"""A synthetic character used by the pipeline tests.

Real art is large and licensed; the tests need something small, deterministic
and shaped like the thing under test. This draws a front-facing face with hair,
irises, lashes, brows, a closed mouth and a torso, using the same colour
families as ``pipeline/palette.mugi.json``.
"""

from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw

SKIN = (252, 224, 200, 255)
HAIR = (112, 88, 68, 255)
IRIS = (12, 122, 96, 255)
LINE = (18, 14, 12, 255)
CLOTH = (238, 226, 210, 255)
WHITE = (250, 250, 250, 255)


def draw(width: int = 600, height: int = 900, eye_shift: int = 0) -> Image.Image:
    """Return a small RGBA character drawing.

    Args:
        width: Canvas width.
        height: Canvas height.
        eye_shift: Pixels to move both eyes down, to vary a test candidate.
    """
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    pen = ImageDraw.Draw(image)

    centre = width // 2
    pen.rounded_rectangle((centre - 150, 520, centre + 150, height - 20), radius=60, fill=CLOTH)
    pen.rectangle((centre - 46, 420, centre + 46, 540), fill=SKIN)
    pen.ellipse((centre - 120, 300, centre + 120, 440), fill=HAIR)
    pen.ellipse((centre - 105, 110, centre + 105, 470), fill=SKIN)
    pen.ellipse((centre - 130, 60, centre + 130, 250), fill=HAIR)
    pen.rectangle((centre - 130, 180, centre - 95, 400), fill=HAIR)
    pen.rectangle((centre + 95, 180, centre + 130, 400), fill=HAIR)

    for side in (-1, 1):
        eye_x = centre + side * 50
        eye_y = 270 + eye_shift
        pen.ellipse((eye_x - 34, eye_y - 28, eye_x + 34, eye_y + 28), fill=LINE)
        pen.ellipse((eye_x - 29, eye_y - 23, eye_x + 29, eye_y + 23), fill=WHITE)
        pen.ellipse((eye_x - 19, eye_y - 19, eye_x + 19, eye_y + 19), fill=IRIS)
        pen.rectangle((eye_x - 32, eye_y - 64, eye_x + 32, eye_y - 54), fill=HAIR)

    pen.rectangle((centre - 36, 388, centre - 6, 394), fill=(96, 46, 40, 255))
    pen.rectangle((centre + 6, 388, centre + 36, 394), fill=(96, 46, 40, 255))
    return image


def array(**kwargs: int) -> np.ndarray:
    """Return :func:`draw` as a writable ``H x W x 4`` uint8 array."""
    return np.array(draw(**kwargs), dtype=np.uint8)
