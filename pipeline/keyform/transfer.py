"""Plan the transfer: source deformation, target base shape, one document out.

For every mapped pair this computes, per keyform,

    target_form = target_reference + Frame(source_reference -> target_reference)
                                     . (source_form - source_reference)

so the reference form reproduces the target's base geometry bit for bit and every
other form is the target's own shape carrying the source's motion. No absolute
source coordinate ever reaches the output.

The function is pure and total: it never raises for a data problem, it collects
diagnostics and marks the plan ``rejected``. A rejected plan is still emitted so
that all forty-one meshes can be fixed in one pass, but the Cubism bridge must
refuse to apply anything whose ``status`` is not ``ready``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from pipeline.keyform import manifest as mf
from pipeline.keyform import meshmap as mm
from pipeline.keyform.frame import DegenerateFrameError, Frame
from pipeline.keyform.frame import fit as fit_frame

PLAN_SCHEMA = "mugi-live2d/keyform-transfer-plan@1"
DEFAULT_TOLERANCE = 1e-6

PRESERVED = (
    "artmesh_id",
    "artmesh_count",
    "vertex_count",
    "triangles",
    "texture_uv",
    "draw_order",
    "clipping",
    "opacity",
    "target_reference_geometry",
)


@dataclass(frozen=True, slots=True)
class Diagnostic:
    """One reason a plan cannot be applied."""

    code: str
    scope: str
    message: str

    def to_json(self) -> dict[str, str]:
        """Return the diagnostic as a plain document."""
        return {"code": self.code, "scope": self.scope, "message": self.message}


def _coverage(
    source: mf.Manifest, target: mf.Manifest, mesh_map: mm.MeshMap
) -> list[Diagnostic]:
    """Check that the mapping accounts for every target mesh, and only real ones."""
    found: list[Diagnostic] = []
    for manifest, wanted in ((source, "source"), (target, "target")):
        if manifest.role != wanted:
            found.append(
                Diagnostic(
                    "role_mismatch",
                    manifest.id,
                    f"expected a {wanted} manifest, got role {manifest.role!r}",
                )
            )

    target_ids = set(target.mesh_ids)
    for missing in sorted(target_ids - mesh_map.targets):
        found.append(
            Diagnostic(
                "unmapped_target",
                missing,
                "target ArtMesh is neither mapped to a source mesh nor explicitly excluded",
            )
        )
    for unknown in sorted(mesh_map.targets - target_ids):
        found.append(
            Diagnostic(
                "unknown_target",
                unknown,
                "the mapping names an ArtMesh the target model does not have",
            )
        )
    source_ids = set(source.mesh_ids)
    for pair in mesh_map.pairs:
        if pair.source not in source_ids:
            found.append(
                Diagnostic(
                    "unknown_source",
                    pair.source,
                    f"the mapping drives {pair.target!r} from an ArtMesh the source does not have",
                )
            )
    return found


def _parameter_checks(
    source: mf.Manifest, target: mf.Manifest, source_mesh: mf.Mesh, scope: str
) -> list[Diagnostic]:
    """Check that the target can hold the coordinates the source forms sit at."""
    found: list[Diagnostic] = []
    for name in source_mesh.parameters:
        theirs = target.parameters.get(name)
        if theirs is None:
            found.append(
                Diagnostic(
                    "unknown_target_parameter",
                    scope,
                    f"the source deforms on {name!r}, which the target model does not declare",
                )
            )
            continue
        ours = source.parameters[name]
        if abs(ours.default - theirs.default) > DEFAULT_TOLERANCE:
            found.append(
                Diagnostic(
                    "default_mismatch",
                    scope,
                    f"{name!r} rests at {ours.default} in the source and {theirs.default} in the "
                    "target, so the two reference forms are not the same pose",
                )
            )
    for form in source_mesh.forms:
        for name, value in form.coordinate:
            theirs = target.parameters.get(name)
            if theirs is None:
                continue
            if not theirs.minimum <= value <= theirs.maximum:
                found.append(
                    Diagnostic(
                        "parameter_range",
                        scope,
                        f"source keyform at {name}={value} is outside the target range "
                        f"[{theirs.minimum}, {theirs.maximum}]",
                    )
                )
    return found


def _forms_for(
    source_mesh: mf.Mesh,
    target_mesh: mf.Mesh,
    source_reference: mf.Keyform,
    target_reference: mf.Keyform,
    frame: Frame,
) -> tuple[list[dict[str, Any]], float]:
    """Build every transferred keyform for one pair, plus its largest motion."""
    base = np.asarray(source_reference.vertices, dtype=np.float64)
    anchor = np.asarray(target_reference.vertices, dtype=np.float64)
    reference_key = source_reference.key

    forms: list[dict[str, Any]] = []
    largest = 0.0
    for form in source_mesh.forms:
        displacement = frame.push(np.asarray(form.vertices, dtype=np.float64) - base)
        vertices = anchor + displacement
        lengths = np.sqrt((displacement**2).sum(axis=1))
        peak = float(lengths.max()) if len(lengths) else 0.0
        largest = max(largest, peak)
        forms.append(
            {
                "key": form.key,
                "coordinate": form.coordinate_json(),
                "is_reference": form.key == reference_key,
                "action": "replace" if target_mesh.form(form.key) is not None else "create",
                "displacement": {
                    "max_px": peak,
                    "rms_px": float(np.sqrt((lengths**2).mean())) if len(lengths) else 0.0,
                },
                "vertices": [[float(x), float(y)] for x, y in vertices],
            }
        )
    return forms, largest


def _pair_plan(
    source: mf.Manifest,
    target: mf.Manifest,
    pair: mm.Pair,
    frame_mode: str,
    ceiling: float | None,
) -> tuple[dict[str, Any] | None, list[Diagnostic]]:
    """Plan one mapped pair, or explain why it cannot be planned."""
    scope = pair.target
    source_mesh, target_mesh = source.mesh(pair.source), target.mesh(pair.target)
    if source_mesh is None or target_mesh is None:
        return None, []  # already reported by the coverage pass

    found = _parameter_checks(source, target, source_mesh, scope)
    if source_mesh.vertex_count != target_mesh.vertex_count:
        found.append(
            Diagnostic(
                "vertex_count_mismatch",
                scope,
                f"source {pair.source!r} has {source_mesh.vertex_count} vertices and the target "
                f"has {target_mesh.vertex_count}; a per-vertex displacement needs both to agree",
            )
        )
        return None, found
    if source_mesh.triangles != target_mesh.triangles:
        found.append(
            Diagnostic(
                "topology_mismatch",
                scope,
                f"source {pair.source!r} and the target share a vertex count but not a triangle "
                "list, so vertex indices do not mean the same thing in both meshes",
            )
        )
        return None, found

    try:
        source_reference = source.reference_form(source_mesh)
        target_reference = target.reference_form(target_mesh)
    except mf.ReferenceFormError as error:
        found.append(Diagnostic("reference_form", scope, str(error)))
        return None, found

    try:
        frame = fit_frame(source_reference.vertices, target_reference.vertices, frame_mode)
    except (DegenerateFrameError, ValueError) as error:
        found.append(Diagnostic("degenerate_frame", scope, str(error)))
        return None, found

    forms, largest = _forms_for(
        source_mesh, target_mesh, source_reference, target_reference, frame
    )
    if not all(np.isfinite(form["vertices"]).all() for form in forms):
        found.append(
            Diagnostic("non_finite_result", scope, "the transfer produced non-finite coordinates")
        )
        return None, found
    if ceiling is not None and largest > ceiling:
        found.append(
            Diagnostic(
                "displacement_over_limit",
                scope,
                f"the largest transferred motion is {largest:.3f} px, over the reviewed ceiling "
                f"of {ceiling:.3f} px; this is what an absolute-coordinate copy looks like",
            )
        )
        return None, found
    if found:
        return None, found

    return {
        "target": pair.target,
        "source": pair.source,
        "note": pair.note,
        "vertex_count": target_mesh.vertex_count,
        "parameters": list(source_mesh.parameters),
        "frame": frame.to_json(),
        "reference_key": source_reference.key,
        "invariant_digest": mf.invariant_digest(target_mesh),
        "max_displacement_px": largest,
        "forms": forms,
    }, []


def plan(
    source: mf.Manifest,
    target: mf.Manifest,
    mesh_map: mm.MeshMap,
    *,
    frame_mode: str | None = None,
    max_displacement: float | None = None,
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the transfer plan for one source, target and reviewed mapping.

    ``frame_mode`` overrides the mapping's default mode; pairs that name their
    own mode keep it, because that choice is reviewed data too.
    """
    default_mode = frame_mode or mesh_map.frame
    ceiling = max_displacement if max_displacement is not None else mesh_map.max_displacement

    diagnostics = _coverage(source, target, mesh_map)
    meshes: list[dict[str, Any]] = []
    for pair in mesh_map.pairs:
        mode = pair.frame or default_mode
        entry, found = _pair_plan(source, target, pair, mode, ceiling)
        diagnostics.extend(found)
        if entry is not None:
            meshes.append(entry)

    planned_forms = sum(len(entry["forms"]) for entry in meshes)
    largest = max((entry["max_displacement_px"] for entry in meshes), default=0.0)
    status = "rejected" if diagnostics else "ready"

    return {
        "schema": PLAN_SCHEMA,
        "status": status,
        "map": mesh_map.id,
        "source_model": source.id,
        "target_model": target.id,
        "generated_from": provenance or {},
        "policy": {
            "frame": default_mode,
            "transfer": "target reference geometry plus source displacement in the target frame",
            "preserved": list(PRESERVED),
            "max_displacement_px": ceiling,
            "apply_only_when": "status == 'ready'",
        },
        "summary": {
            "target_artmeshes": len(target.meshes),
            "mapped": len(mesh_map.pairs),
            "excluded": len(mesh_map.excluded),
            "planned_meshes": len(meshes),
            "planned_forms": planned_forms,
            "max_displacement_px": largest,
            "diagnostics": len(diagnostics),
        },
        "target_invariants": {
            "artmesh_count": len(target.meshes),
            "meshes": {mesh.id: mf.invariant_digest(mesh) for mesh in target.meshes},
        },
        "meshes": meshes,
        "excluded": [
            {"target": entry.target, "reason": entry.reason} for entry in mesh_map.excluded
        ],
        "diagnostics": [item.to_json() for item in diagnostics],
    }
