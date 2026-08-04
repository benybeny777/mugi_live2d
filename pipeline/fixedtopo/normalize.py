"""Fit measured landmarks onto the contract's anchors.

The master rig is fixed, so the picture moves: a similarity transform maps the
input's eye line and mouth onto the anchors the rig was built around. Scaling
the whole canvas would only preserve the framing the input happened to have.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from PIL import Image

Point = tuple[float, float]

RESAMPLE = {
    "nearest": Image.Resampling.NEAREST,
    "bilinear": Image.Resampling.BILINEAR,
    "bicubic": Image.Resampling.BICUBIC,
    "lanczos": Image.Resampling.LANCZOS,
}


@dataclass(frozen=True, slots=True)
class Similarity:
    """A uniform scale, rotation and translation in image coordinates."""

    scale: float
    rotation: float
    translation: Point

    @property
    def matrix(self) -> NDArray[np.float64]:
        """Return the 2x3 forward transform as a matrix."""
        cos = self.scale * np.cos(self.rotation)
        sin = self.scale * np.sin(self.rotation)
        return np.array(
            [[cos, -sin, self.translation[0]], [sin, cos, self.translation[1]]], dtype=np.float64
        )

    def apply(self, points: Sequence[Point]) -> list[Point]:
        """Map points from source space into canvas space."""
        matrix = self.matrix
        return [
            (
                float(matrix[0, 0] * x + matrix[0, 1] * y + matrix[0, 2]),
                float(matrix[1, 0] * x + matrix[1, 1] * y + matrix[1, 2]),
            )
            for x, y in points
        ]

    def apply_box(self, box: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
        """Map an axis-aligned box and return its transformed bounds."""
        x0, y0, x1, y1 = box
        corners = self.apply([(x0, y0), (x1, y0), (x0, y1), (x1, y1)])
        xs = [point[0] for point in corners]
        ys = [point[1] for point in corners]
        return (
            int(round(min(xs))),
            int(round(min(ys))),
            int(round(max(xs))),
            int(round(max(ys))),
        )

    def inverse_coefficients(self) -> tuple[float, ...]:
        """Return the canvas-to-source coefficients PIL's AFFINE transform wants."""
        matrix = np.vstack([self.matrix, [0.0, 0.0, 1.0]])
        inverse = np.linalg.inv(matrix)
        return tuple(float(value) for value in inverse[:2].ravel())


def fit(
    source: Sequence[Point], target: Sequence[Point], allow_rotation: bool = True
) -> Similarity:
    """Return the least-squares similarity that maps ``source`` onto ``target``.

    This is the closed-form Umeyama solution, so the same points always give the
    same transform; there is no iteration and no random initialisation.
    """
    if len(source) != len(target) or len(source) < 2:
        raise ValueError("similarity fitting needs at least two matched point pairs")
    left = np.asarray(source, dtype=np.float64)
    right = np.asarray(target, dtype=np.float64)
    left_mean, right_mean = left.mean(axis=0), right.mean(axis=0)
    left_centred, right_centred = left - left_mean, right - right_mean

    variance = float((left_centred**2).sum())
    if variance <= 0.0:
        raise ValueError("source landmarks are degenerate")

    if allow_rotation:
        covariance = right_centred.T @ left_centred
        u, singular, vt = np.linalg.svd(covariance)
        correction = np.eye(2)
        if np.linalg.det(u @ vt) < 0:
            correction[1, 1] = -1.0
        rotation_matrix = u @ correction @ vt
        scale = float((singular * np.diag(correction)).sum()) / variance
        rotation = float(np.arctan2(rotation_matrix[1, 0], rotation_matrix[0, 0]))
    else:
        scale = float((left_centred * right_centred).sum()) / variance
        rotation = 0.0

    cos, sin = scale * np.cos(rotation), scale * np.sin(rotation)
    translation = (
        float(right_mean[0] - (cos * left_mean[0] - sin * left_mean[1])),
        float(right_mean[1] - (sin * left_mean[0] + cos * left_mean[1])),
    )
    return Similarity(scale=scale, rotation=rotation, translation=translation)


def residuals(
    transform: Similarity, source: Sequence[Point], target: Sequence[Point]
) -> list[float]:
    """Return the per-point fitting error in canvas pixels."""
    mapped = transform.apply(source)
    return [float(np.hypot(a[0] - b[0], a[1] - b[1])) for a, b in zip(mapped, target)]


def resample(
    rgba: NDArray[np.uint8],
    transform: Similarity,
    canvas: tuple[int, int],
    filter_name: str = "bicubic",
) -> NDArray[np.uint8]:
    """Render the source image into the contract canvas under ``transform``.

    Alpha is premultiplied first so that resampling never drags background
    colour into the character's outline, then unpremultiplied afterwards.
    """
    if filter_name not in RESAMPLE:
        raise ValueError(f"unknown resample filter: {filter_name}")
    scaled = rgba.astype(np.float32)
    alpha = scaled[..., 3:4] / 255.0
    premultiplied = np.concatenate((scaled[..., :3] * alpha, scaled[..., 3:4]), axis=-1)
    image = Image.fromarray(np.clip(premultiplied, 0, 255).astype(np.uint8), mode="RGBA")
    warped = image.transform(
        canvas,
        Image.Transform.AFFINE,
        transform.inverse_coefficients(),
        resample=RESAMPLE[filter_name],
    )

    result = np.asarray(warped, dtype=np.float32)
    out_alpha = np.maximum(result[..., 3:4] / 255.0, 1e-4)
    colour = np.clip(result[..., :3] / out_alpha, 0, 255)
    return np.concatenate((colour, result[..., 3:4]), axis=-1).round().astype(np.uint8)
