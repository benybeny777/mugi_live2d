"""Post-apply proof that Cubism saved exactly the approved transfer plan."""

from __future__ import annotations

from typing import Any

import numpy as np

from pipeline.keyform import manifest as mf
from pipeline.keyform.transfer import PLAN_SCHEMA

# Cubism's CMO3 writer round-trips Java float positions with up to roughly
# 3e-5 quantisation in this model.  This ceiling remains 200x tighter than the
# smallest visually meaningful transfer displacement used by the QA fixtures.
POSITION_TOLERANCE = 5e-5


def verify(plan: dict[str, Any], actual: mf.Manifest) -> dict[str, Any]:
    """Compare a re-extracted Cubism document with its approved plan."""
    problems: list[dict[str, str]] = []

    def problem(code: str, scope: str, message: str) -> None:
        problems.append({"code": code, "scope": scope, "message": message})

    if plan.get("schema") != PLAN_SCHEMA:
        problem("plan_schema", "plan", f"unsupported plan schema {plan.get('schema')!r}")
    if plan.get("status") != "ready":
        problem("plan_status", "plan", f"plan status is {plan.get('status')!r}, not 'ready'")
    if actual.role != "target":
        problem("role_mismatch", actual.id, f"actual manifest role is {actual.role!r}")

    invariants = plan.get("target_invariants", {})
    expected_count = invariants.get("artmesh_count")
    if expected_count != len(actual.meshes):
        problem(
            "artmesh_count",
            actual.id,
            f"actual has {len(actual.meshes)} ArtMeshes; plan requires {expected_count}",
        )
    expected_structures = invariants.get("meshes", {})
    expected_keyforms = invariants.get("keyforms")
    if not isinstance(expected_keyforms, dict):
        problem("missing_keyform_invariants", "plan", "plan cannot prove excluded geometry")
        expected_keyforms = {}

    planned = {str(entry["target"]): entry for entry in plan.get("meshes", [])}
    excluded = {str(entry["target"]) for entry in plan.get("excluded", [])}
    for mesh in actual.meshes:
        expected_structure = expected_structures.get(mesh.id)
        if expected_structure is None:
            problem("unaccounted_mesh", mesh.id, "mesh was not present in target invariants")
            continue
        if mf.invariant_digest(mesh) != expected_structure:
            problem(
                "invariant_changed",
                mesh.id,
                "topology, UV, draw order, clipping or opacity changed",
            )

        mesh_plan = planned.get(mesh.id)
        if mesh_plan is None:
            if mesh.id not in excluded:
                problem("unplanned_mesh", mesh.id, "mesh is neither planned nor excluded")
            elif expected_keyforms.get(mesh.id) != mf.keyform_digest(mesh):
                problem("excluded_keyforms_changed", mesh.id, "excluded mesh deformation changed")
            continue

        forms = {form.key: form for form in mesh.forms}
        expected_forms = mesh_plan.get("forms", [])
        if len(forms) != len(expected_forms):
            problem(
                "keyform_count",
                mesh.id,
                f"actual has {len(forms)} forms; plan requires {len(expected_forms)}",
            )
            continue
        for form_plan in expected_forms:
            key = str(form_plan["key"])
            form = forms.get(key)
            if form is None:
                problem("keyform_missing", mesh.id, f"missing form at {key}")
                continue
            expected = np.asarray(form_plan["vertices"], dtype=np.float64)
            observed = np.asarray(form.vertices, dtype=np.float64)
            if expected.shape != observed.shape or not np.allclose(
                expected, observed, rtol=0.0, atol=POSITION_TOLERANCE
            ):
                delta = (
                    float(np.max(np.abs(expected - observed)))
                    if expected.shape == observed.shape
                    else float("inf")
                )
                problem("vertices_mismatch", mesh.id, f"{key} differs by up to {delta:.9g}")

    missing = (set(expected_structures) | set(planned) | excluded) - set(actual.mesh_ids)
    for mesh_id in sorted(missing):
        problem("mesh_missing", mesh_id, "required target ArtMesh is absent")

    return {
        "schema": "mugi-live2d/keyform-verification@1",
        "status": "rejected" if problems else "ready",
        "model": actual.id,
        "artmeshes": len(actual.meshes),
        "planned_meshes": len(planned),
        "verified_forms": sum(len(entry.get("forms", [])) for entry in planned.values()),
        "problems": problems,
    }
