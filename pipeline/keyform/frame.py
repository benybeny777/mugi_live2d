"""The per-mesh local frame that makes a source displacement mean something on the target.

A keyform displacement is a vector field in the source mesh's own space. Adding
it to the target unchanged assumes the two meshes are the same size and sit in
the same place, which is exactly the assumption that put Mugi's hair in Hiyori's
coordinates. Instead we fit the map that takes the *source reference shape* onto
the *target reference shape* and push the displacement through its linear part.

``similarity`` is the default: uniform scale, rotation and translation, so a
transferred blink keeps its shape and only changes size and orientation.
``affine`` additionally allows anisotropic stretch and shear, for a pair whose
base shapes genuinely differ in aspect. Both are closed-form least squares, so
the same two reference shapes always give the same frame.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from pipeline.fixedtopo import normalize

MODES = ("similarity", "affine")
MIN_EXTENT = 1e-6
MIN_CONDITION = 1e-8

Point = tuple[float, float]
Matrix = tuple[tuple[float, float], tuple[float, float]]


class DegenerateFrameError(ValueError):
    """Raised when a reference shape carries no usable frame."""


def extent(points: NDArray[np.float64]) -> float:
    """Return the RMS radius of a point set about its own centroid."""
    if points.size == 0:
        return 0.0
    centred = points - points.mean(axis=0)
    return float(np.sqrt((centred**2).sum(axis=1).mean()))


@dataclass(frozen=True, slots=True)
class Frame:
    """The reference-to-reference map for one mesh pair."""

    mode: str
    linear: Matrix
    translation: Point
    source_extent: float
    target_extent: float
    residual_rms: float

    @property
    def matrix(self) -> NDArray[np.float64]:
        """Return the linear part as a 2x2 matrix."""
        return np.asarray(self.linear, dtype=np.float64)

    @property
    def scale(self) -> float:
        """Return the area-preserving scale factor of the linear part."""
        return float(np.sqrt(abs(np.linalg.det(self.matrix))))

    def push(self, displacements: NDArray[np.float64]) -> NDArray[np.float64]:
        """Carry source-space displacements into target space.

        Only the linear part applies: a displacement is a difference of two
        points, so the translation has already cancelled.
        """
        return np.asarray(displacements, dtype=np.float64) @ self.matrix.T

    def apply(self, points: NDArray[np.float64]) -> NDArray[np.float64]:
        """Map source-space positions into target space."""
        return np.asarray(points, dtype=np.float64) @ self.matrix.T + np.asarray(self.translation)

    def to_json(self) -> dict[str, object]:
        """Return the frame as a plain document."""
        return {
            "mode": self.mode,
            "linear": [list(row) for row in self.linear],
            "translation": list(self.translation),
            "scale": self.scale,
            "source_extent_px": self.source_extent,
            "target_extent_px": self.target_extent,
            "residual_rms_px": self.residual_rms,
        }


def _residual_rms(
    linear: NDArray[np.float64],
    translation: NDArray[np.float64],
    source: NDArray[np.float64],
    target: NDArray[np.float64],
) -> float:
    """Return how far the fitted map leaves the reference shapes apart."""
    mapped = source @ linear.T + translation
    return float(np.sqrt(((mapped - target) ** 2).sum(axis=1).mean()))


#: Why a reference shape with no extent cannot carry a frame, per role.
_NO_EXTENT = {
    "source": "the source reference shape has no extent, so its displacements have no scale",
    "target": "the target reference shape has no extent, so it has no shape to deform",
}


def _usable(points: NDArray[np.float64], role: str) -> float:
    """Return the RMS radius, refusing a shape that cannot fix a 2D frame.

    A collinear ArtMesh would leave the direction across the line unconstrained,
    so the transfer would be free to put a perpendicular displacement anywhere.
    Real ArtMeshes have area; a flat one is corrupt data, not a special case.
    """
    radius = extent(points)
    if radius <= MIN_EXTENT:
        raise DegenerateFrameError(_NO_EXTENT[role])
    singular = np.linalg.svd(points - points.mean(axis=0), compute_uv=False)
    if singular[-1] / singular[0] < MIN_CONDITION:
        raise DegenerateFrameError(
            f"the {role} reference shape is collinear, so it does not fix a frame"
        )
    return radius


def _affine(
    source: NDArray[np.float64], target: NDArray[np.float64]
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Solve the least-squares affine map."""
    if len(source) < 3:
        raise DegenerateFrameError("an affine frame needs at least three vertices")
    design = np.hstack([source, np.ones((len(source), 1))])
    solution, *_ = np.linalg.lstsq(design, target, rcond=None)
    return solution[:2].T, solution[2]


def fit(
    source: Sequence[Point], target: Sequence[Point], mode: str = "similarity"
) -> Frame:
    """Return the frame that maps the source reference shape onto the target's."""
    if mode not in MODES:
        raise ValueError(f"unknown frame mode: {mode!r}; expected one of {MODES}")
    left = np.asarray(source, dtype=np.float64)
    right = np.asarray(target, dtype=np.float64)
    if left.shape != right.shape:
        raise ValueError(f"reference shapes disagree: {left.shape} against {right.shape}")
    if not (np.isfinite(left).all() and np.isfinite(right).all()):
        raise DegenerateFrameError("reference shapes contain non-finite coordinates")

    source_extent, target_extent = _usable(left, "source"), _usable(right, "target")

    if mode == "similarity":
        fitted = normalize.fit(
            [(float(x), float(y)) for x, y in left],
            [(float(x), float(y)) for x, y in right],
            allow_rotation=True,
        )
        matrix = fitted.matrix
        linear, translation = matrix[:, :2], matrix[:, 2]
    else:
        linear, translation = _affine(left, right)

    if not (np.isfinite(linear).all() and np.isfinite(translation).all()):
        raise DegenerateFrameError("the fitted frame is not finite")
    if abs(float(np.linalg.det(linear))) <= MIN_CONDITION:
        raise DegenerateFrameError("the fitted frame collapses the mesh onto a line or a point")

    return Frame(
        mode=mode,
        linear=(
            (float(linear[0, 0]), float(linear[0, 1])),
            (float(linear[1, 0]), float(linear[1, 1])),
        ),
        translation=(float(translation[0]), float(translation[1])),
        source_extent=source_extent,
        target_extent=target_extent,
        residual_rms=_residual_rms(linear, translation, left, right),
    )
