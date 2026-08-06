from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_script(name: str):
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_generated_vrm_passes_structural_validation(tmp_path: Path) -> None:
    builder = _load_script("build_vrm")
    validator = _load_script("validate_vrm")
    output = tmp_path / "mugi.vrm"

    result = builder.build_vrm(
        ROOT / "work" / "psd" / "hiyori" / "mugi-hiyori-compatible-final.psd",
        output,
        256,
    )

    assert result["layers"] == 18
    assert result["meshes"] == 18
    assert result["vertices"] == 459
    assert result["deformableMeshes"] == 16
    assert result["gradientWeightedMeshes"] == 5
    assert result["facialGridMeshes"] == 8
    assert validator.validate(output) == []
    document, _ = validator.read_glb(output)
    vrm = document["extensions"]["VRMC_vrm"]
    assert set(vrm["expressions"]["preset"]) >= {
        "blink",
        "aa",
        "happy",
        "sad",
        "angry",
        "relaxed",
        "surprised",
        "lookLeft",
        "lookRight",
        "lookUp",
        "lookDown",
    }
    assert set(vrm["expressions"]["custom"]) == {"breath", "idleLeft", "idleRight"}
    assert len(document["meshes"]) == 18
    animated_meshes = [
        mesh for mesh in document["meshes"] if mesh["primitives"][0].get("targets")
    ]
    assert len(animated_meshes) == 16
    mesh_by_name = {mesh["name"]: mesh for mesh in document["meshes"]}
    assert mesh_by_name["torsoMesh"]["extras"]["grid"] == [4, 8]
    assert mesh_by_name["screen_left_armMesh"]["extras"]["gradientWeights"] is True
    assert mesh_by_name["faceMesh"]["extras"]["grid"] == [1, 1]
    assert mesh_by_name["left_eye_whiteMesh"]["extras"]["grid"] == [4, 2]
    assert mesh_by_name["mouthMesh"]["extras"]["grid"] == [5, 2]
    assert mesh_by_name["mouth_insideMesh"]["extras"]["grid"] == [5, 2]


def test_validator_rejects_non_glb(tmp_path: Path) -> None:
    validator = _load_script("validate_vrm")
    invalid = tmp_path / "invalid.vrm"
    invalid.write_bytes(b"not a vrm")

    assert validator.validate(invalid) == ["file is too short to be a GLB"]
