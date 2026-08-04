"""Small hand-built manifests for the keyform transfer tests.

Real Cubism exports are large and proprietary, so the tests build the smallest
documents that still exercise the rules: a quad mesh, one parameter with a
non-zero default, and a reference form that is deliberately *not* first in the
list so that nothing can pass by relying on ordering.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

from pipeline.keyform.manifest import MANIFEST_SCHEMA
from pipeline.keyform.meshmap import MAP_SCHEMA

Vertices = list[list[float]]

QUAD_TRIANGLES = [[0, 1, 2], [0, 2, 3]]
EYE_OPEN = "ParamEyeLOpen"


def quad(cx: float, cy: float, half: float) -> Vertices:
    """Return an axis-aligned quad, counter-clockwise from the top left."""
    return [
        [cx - half, cy - half],
        [cx + half, cy - half],
        [cx + half, cy + half],
        [cx - half, cy + half],
    ]


def translated(vertices: Sequence[Sequence[float]], dx: float, dy: float) -> Vertices:
    """Shift every vertex."""
    return [[x + dx, y + dy] for x, y in vertices]


def scaled(
    vertices: Sequence[Sequence[float]],
    factor: float,
    about: tuple[float, float] = (0.0, 0.0),
) -> Vertices:
    """Scale every vertex about a fixed point."""
    return [
        [about[0] + (x - about[0]) * factor, about[1] + (y - about[1]) * factor]
        for x, y in vertices
    ]


def rotated(
    vertices: Sequence[Sequence[float]],
    degrees: float,
    about: tuple[float, float] = (0.0, 0.0),
) -> Vertices:
    """Rotate every vertex about a fixed point."""
    angle = math.radians(degrees)
    cos, sin = math.cos(angle), math.sin(angle)
    out: Vertices = []
    for x, y in vertices:
        dx, dy = x - about[0], y - about[1]
        out.append([about[0] + cos * dx - sin * dy, about[1] + sin * dx + cos * dy])
    return out


def parameter(
    identifier: str = EYE_OPEN,
    minimum: float = 0.0,
    maximum: float = 1.0,
    default: float = 1.0,
) -> dict[str, Any]:
    """Return one parameter declaration."""
    return {
        "id": identifier,
        "name": identifier,
        "minimum": minimum,
        "maximum": maximum,
        "default": default,
    }


def mesh(
    mesh_id: str,
    forms: Sequence[tuple[dict[str, float], Sequence[Sequence[float]]]],
    *,
    parameters: Sequence[str] = (EYE_OPEN,),
    triangles: Sequence[Sequence[int]] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """Return one ArtMesh document from ``(coordinate, vertices)`` pairs."""
    document: dict[str, Any] = {
        "id": mesh_id,
        "name": mesh_id,
        "vertex_count": len(forms[0][1]),
        "parameters": list(parameters),
        "triangles": [list(triangle) for triangle in (triangles or QUAD_TRIANGLES)],
        "forms": [
            {"coordinate": dict(coordinate), "vertices": [list(v) for v in vertices]}
            for coordinate, vertices in forms
        ],
    }
    document.update(extra)
    return document


def eye_mesh(
    mesh_id: str,
    centre: tuple[float, float],
    half: float,
    *,
    closed: Sequence[Sequence[float]] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """Return a quad eye whose open form sits at the parameter default of 1.0.

    The closed form is listed first on purpose: position in the list must never
    be what identifies the reference shape.
    """
    open_shape = quad(centre[0], centre[1], half)
    shut = closed if closed is not None else [
        [x, centre[1]] for x, _ in open_shape
    ]
    return mesh(
        mesh_id,
        [({EYE_OPEN: 0.0}, shut), ({EYE_OPEN: 1.0}, open_shape)],
        **extra,
    )


def manifest(
    role: str,
    meshes: Sequence[dict[str, Any]],
    *,
    model_id: str | None = None,
    parameters: Sequence[dict[str, Any]] | None = None,
    canvas: tuple[int, int] = (2976, 4175),
) -> dict[str, Any]:
    """Return a whole manifest document."""
    return {
        "schema": MANIFEST_SCHEMA,
        "model": {
            "id": model_id or f"test-{role}",
            "role": role,
            "canvas": {"width": canvas[0], "height": canvas[1]},
        },
        "parameters": [dict(item) for item in (parameters or [parameter()])],
        "meshes": [dict(item) for item in meshes],
    }


def mesh_map(
    pairs: Sequence[tuple[str, str]],
    *,
    excluded: Sequence[tuple[str, str]] = (),
    frame: str = "similarity",
    limits: dict[str, float] | None = None,
    map_id: str = "test-map",
) -> dict[str, Any]:
    """Return a mesh mapping document from ``(target, source)`` pairs."""
    return {
        "schema": MAP_SCHEMA,
        "id": map_id,
        "source_model": "test-source",
        "target_model": "test-target",
        "frame": frame,
        "limits": dict(limits or {}),
        "pairs": [{"target": target, "source": source} for target, source in pairs],
        "excluded": [{"target": target, "reason": reason} for target, reason in excluded],
    }
