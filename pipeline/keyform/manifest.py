"""The keyform manifest: one model's ArtMeshes, topology and keyforms, as data.

A manifest is what the Cubism bridge extracts and what the planner consumes. It
is deliberately explicit about two things the first transfer attempt guessed at:

* every keyform carries the *parameter coordinate* it sits at, so a source form
  and a target form are matched by identity rather than by list position; and
* every parameter declares its default, so the reference form is the form whose
  coordinate is the defaults -- proven from the document, not assumed to be
  ``forms[0]``.

Loading validates everything that must hold for the document to mean anything at
all: schema, unique ids, declared vertex counts, finite coordinates, in-range
parameter values, and in-range triangle indices. Problems that only exist
*between* two manifests -- a missing mapping, a vertex-count disagreement, a
mesh with no reference form -- are reported by the planner as diagnostics so
that one bad mesh does not hide the other forty.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

MANIFEST_SCHEMA = "mugi-live2d/keyform-manifest@1"
ROLES = ("source", "target")
COORDINATE_PLACES = 6

Point = tuple[float, float]
Triangle = tuple[int, int, int]
Coordinate = tuple[tuple[str, float], ...]


class ManifestError(ValueError):
    """Raised when a manifest cannot be trusted as written."""


class ReferenceFormError(ValueError):
    """Raised when a mesh does not have exactly one identifiable reference form."""


def _canonical_value(value: float) -> str:
    """Format a parameter value for keying; ``-0.0`` and ``0.0`` must not disagree."""
    return f"{value + 0.0:.{COORDINATE_PLACES}f}"


def coordinate_key(coordinate: Iterable[tuple[str, float]]) -> str:
    """Return the canonical, order-independent key for a parameter coordinate."""
    parts = sorted((str(name), float(value)) for name, value in coordinate)
    return ";".join(f"{name}={_canonical_value(value)}" for name, value in parts)


def _number(value: Any, where: str) -> float:
    """Return ``value`` as a finite float, or explain which field was not one."""
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ManifestError(f"{where}: expected a number, got {value!r}") from error
    if not math.isfinite(number):
        raise ManifestError(f"{where}: coordinates must be finite, got {value!r}")
    return number


def _point(value: Any, where: str) -> Point:
    """Read one ``[x, y]`` pair."""
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ManifestError(f"{where}: expected an [x, y] pair, got {value!r}")
    return _number(value[0], f"{where}.x"), _number(value[1], f"{where}.y")


@dataclass(frozen=True, slots=True)
class Parameter:
    """One Cubism parameter, including the default that defines the rest pose."""

    id: str
    name: str
    minimum: float
    maximum: float
    default: float


@dataclass(frozen=True, slots=True)
class Keyform:
    """One mesh shape, pinned to the parameter coordinate it belongs to."""

    coordinate: Coordinate
    vertices: tuple[Point, ...]

    @property
    def key(self) -> str:
        """Return the canonical key for this form's parameter coordinate."""
        return coordinate_key(self.coordinate)

    def coordinate_json(self) -> dict[str, float]:
        """Return the coordinate as a plain mapping for serialisation."""
        return {name: value for name, value in self.coordinate}


@dataclass(frozen=True, slots=True)
class Mesh:
    """One ArtMesh: fixed topology plus every keyform recorded for it."""

    id: str
    name: str
    vertex_count: int
    parameters: tuple[str, ...]
    forms: tuple[Keyform, ...]
    triangles: tuple[Triangle, ...]
    uvs: tuple[Point, ...] = ()
    draw_order: int | None = None
    clipped_by: tuple[str, ...] = ()
    opacity: float | None = None

    def form(self, key: str) -> Keyform | None:
        """Return the form sitting at one parameter coordinate, if it exists."""
        for candidate in self.forms:
            if candidate.key == key:
                return candidate
        return None


@dataclass(frozen=True, slots=True)
class Manifest:
    """A parsed keyform manifest for one model."""

    id: str
    role: str
    canvas: tuple[int, int]
    parameters: dict[str, Parameter]
    meshes: tuple[Mesh, ...]
    raw: dict[str, Any] = field(repr=False, default_factory=dict)

    @property
    def mesh_ids(self) -> tuple[str, ...]:
        """Return every ArtMesh id in document order."""
        return tuple(mesh.id for mesh in self.meshes)

    def mesh(self, mesh_id: str) -> Mesh | None:
        """Return one ArtMesh by id."""
        for mesh in self.meshes:
            if mesh.id == mesh_id:
                return mesh
        return None

    def reference_key(self, mesh: Mesh) -> str:
        """Return the coordinate key that identifies ``mesh``'s reference form."""
        return coordinate_key((name, self.parameters[name].default) for name in mesh.parameters)

    def reference_form(self, mesh: Mesh) -> Keyform:
        """Return the one form at the parameter defaults.

        Ordering is not evidence, so this refuses to guess: a mesh with no form
        at the defaults, or with two, is a mesh whose base shape is unknown.
        """
        wanted = self.reference_key(mesh)
        matches = [form for form in mesh.forms if form.key == wanted]
        if not matches:
            where = wanted or "no parameters"
            raise ReferenceFormError(
                f"{mesh.id}: no keyform sits at the parameter defaults ({where})"
            )
        if len(matches) > 1:
            raise ReferenceFormError(
                f"{mesh.id}: {len(matches)} keyforms claim the parameter defaults ({wanted})"
            )
        return matches[0]


def _parameters(data: dict[str, Any]) -> dict[str, Parameter]:
    """Read and check the parameter table."""
    table: dict[str, Parameter] = {}
    for index, entry in enumerate(data.get("parameters", [])):
        where = f"parameters[{index}]"
        identifier = str(entry.get("id", "")).strip()
        if not identifier:
            raise ManifestError(f"{where}: a parameter needs a non-empty id")
        if identifier in table:
            raise ManifestError(f"{where}: duplicate parameter id {identifier!r}")
        minimum = _number(entry["minimum"], f"{where}.minimum")
        maximum = _number(entry["maximum"], f"{where}.maximum")
        default = _number(entry["default"], f"{where}.default")
        if not minimum <= default <= maximum:
            raise ManifestError(
                f"{where}: default {default} is outside [{minimum}, {maximum}] for {identifier!r}"
            )
        table[identifier] = Parameter(
            id=identifier,
            name=str(entry.get("name", identifier)),
            minimum=minimum,
            maximum=maximum,
            default=default,
        )
    return table


def _triangles(entry: dict[str, Any], mesh_id: str, vertex_count: int) -> tuple[Triangle, ...]:
    """Read the index list that fixes this mesh's topology."""
    if "triangles" not in entry:
        raise ManifestError(f"{mesh_id}: triangles are required so topology can be compared")
    triangles: list[Triangle] = []
    for index, item in enumerate(entry["triangles"]):
        where = f"{mesh_id}.triangles[{index}]"
        if not isinstance(item, (list, tuple)) or len(item) != 3:
            raise ManifestError(f"{where}: expected three vertex indices, got {item!r}")
        corners = tuple(int(value) for value in item)
        if len(set(corners)) != 3:
            raise ManifestError(f"{where}: a triangle needs three distinct corners, got {item!r}")
        if any(value < 0 or value >= vertex_count for value in corners):
            raise ManifestError(f"{where}: index out of range for {vertex_count} vertices")
        triangles.append((corners[0], corners[1], corners[2]))
    if not triangles:
        raise ManifestError(f"{mesh_id}: triangles must not be empty")
    return tuple(triangles)


def _forms(
    entry: dict[str, Any], mesh_id: str, names: tuple[str, ...], table: dict[str, Parameter]
) -> tuple[Keyform, ...]:
    """Read every keyform, checking its coordinate and its vertex count."""
    vertex_count = int(entry["vertex_count"])
    declared = set(names)
    forms: list[Keyform] = []
    seen: dict[str, int] = {}
    for index, item in enumerate(entry.get("forms", [])):
        where = f"{mesh_id}.forms[{index}]"
        raw_coordinate = item.get("coordinate", {})
        if not isinstance(raw_coordinate, dict):
            raise ManifestError(f"{where}: coordinate must be a parameter-to-value mapping")
        if set(raw_coordinate) != declared:
            raise ManifestError(
                f"{where}: coordinate names {sorted(raw_coordinate)} do not match "
                f"the mesh parameters {sorted(declared)}"
            )
        coordinate: list[tuple[str, float]] = []
        for name in sorted(raw_coordinate):
            value = _number(raw_coordinate[name], f"{where}.coordinate.{name}")
            parameter = table[name]
            if not parameter.minimum <= value <= parameter.maximum:
                raise ManifestError(
                    f"{where}: {name}={value} is outside "
                    f"[{parameter.minimum}, {parameter.maximum}]"
                )
            coordinate.append((name, value))

        vertices = item.get("vertices", [])
        if len(vertices) != vertex_count:
            raise ManifestError(
                f"{where}: {len(vertices)} vertices but the mesh declares {vertex_count}"
            )
        form = Keyform(
            coordinate=tuple(coordinate),
            vertices=tuple(
                _point(vertex, f"{where}.vertices[{n}]") for n, vertex in enumerate(vertices)
            ),
        )
        if form.key in seen:
            raise ManifestError(
                f"{where}: parameter coordinate already used by forms[{seen[form.key]}]; "
                "a coordinate must identify exactly one form"
            )
        seen[form.key] = index
        forms.append(form)
    if not forms:
        raise ManifestError(f"{mesh_id}: a mesh needs at least one keyform")
    return tuple(forms)


def _mesh(entry: dict[str, Any], index: int, table: dict[str, Parameter]) -> Mesh:
    """Read one ArtMesh."""
    mesh_id = str(entry.get("id", "")).strip()
    if not mesh_id:
        raise ManifestError(f"meshes[{index}]: an ArtMesh needs a non-empty id")

    vertex_count = int(entry.get("vertex_count", 0))
    if vertex_count < 1:
        raise ManifestError(f"{mesh_id}: vertex_count must be at least 1")

    names = tuple(str(name) for name in entry.get("parameters", []))
    if len(set(names)) != len(names):
        raise ManifestError(f"{mesh_id}: duplicate parameter in the mesh parameter list")
    unknown = [name for name in names if name not in table]
    if unknown:
        raise ManifestError(f"{mesh_id}: undeclared parameters: {', '.join(sorted(unknown))}")

    uvs = entry.get("uvs")
    if uvs is not None and len(uvs) != vertex_count:
        raise ManifestError(f"{mesh_id}: {len(uvs)} uvs but the mesh declares {vertex_count}")

    opacity = entry.get("opacity")
    return Mesh(
        id=mesh_id,
        name=str(entry.get("name", mesh_id)),
        vertex_count=vertex_count,
        parameters=names,
        forms=_forms(entry, mesh_id, names, table),
        triangles=_triangles(entry, mesh_id, vertex_count),
        uvs=tuple(_point(uv, f"{mesh_id}.uvs[{n}]") for n, uv in enumerate(uvs or ())),
        draw_order=None if entry.get("draw_order") is None else int(entry["draw_order"]),
        clipped_by=tuple(str(name) for name in entry.get("clipped_by", ())),
        opacity=None if opacity is None else _number(opacity, f"{mesh_id}.opacity"),
    )


def parse(data: dict[str, Any]) -> Manifest:
    """Validate and convert an already-decoded manifest document."""
    schema = data.get("schema")
    if schema != MANIFEST_SCHEMA:
        raise ManifestError(
            f"unsupported manifest schema: {schema!r}; expected {MANIFEST_SCHEMA!r}"
        )

    model = data.get("model", {})
    identifier = str(model.get("id", "")).strip()
    if not identifier:
        raise ManifestError("model.id must name the model this manifest describes")
    role = str(model.get("role", "")).strip()
    if role not in ROLES:
        raise ManifestError(f"model.role must be one of {ROLES}, got {role!r}")

    canvas = model.get("canvas", {})
    width, height = int(canvas.get("width", 0)), int(canvas.get("height", 0))
    if width < 1 or height < 1:
        raise ManifestError("model.canvas needs a positive width and height")

    table = _parameters(data)
    meshes = tuple(
        _mesh(entry, index, table) for index, entry in enumerate(data.get("meshes", []))
    )
    if not meshes:
        raise ManifestError("a manifest needs at least one ArtMesh")
    seen: set[str] = set()
    for mesh in meshes:
        if mesh.id in seen:
            raise ManifestError(f"duplicate ArtMesh id: {mesh.id!r}")
        seen.add(mesh.id)

    return Manifest(
        id=identifier,
        role=role,
        canvas=(width, height),
        parameters=table,
        meshes=meshes,
        raw=data,
    )


def load(path: Path | str) -> Manifest:
    """Read and validate a manifest document from disk."""
    return parse(json.loads(Path(path).read_text(encoding="utf-8")))


def invariant_digest(mesh: Mesh) -> str:
    """Digest everything a transfer must leave alone about one ArtMesh.

    The planner never emits these fields, so the bridge can re-extract after
    applying a plan and prove that ids, topology, UVs, draw order, clipping and
    opacity came through untouched.
    """
    payload = {
        "id": mesh.id,
        "vertex_count": mesh.vertex_count,
        "triangles": [list(triangle) for triangle in mesh.triangles],
        "uvs": [list(uv) for uv in mesh.uvs] or None,
        "draw_order": mesh.draw_order,
        "clipped_by": list(mesh.clipped_by),
        "opacity": mesh.opacity,
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def topology_digest(mesh: Mesh) -> str:
    """Digest only the fixed topology, so meshes can be paired by shape."""
    payload = {
        "vertex_count": mesh.vertex_count,
        "triangles": [list(triangle) for triangle in mesh.triangles],
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
