from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_release_validator():
    path = ROOT / "scripts" / "validate_vrm_release.py"
    spec = importlib.util.spec_from_file_location("validate_vrm_release", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_vrm_release_quality_gate() -> None:
    validator = _load_release_validator()

    errors, metrics = validator.validate_release(ROOT)

    assert errors == []
    assert metrics == {
        "bytes": (ROOT / "exports" / "vrm" / "mugi.vrm").stat().st_size,
        "meshes": 18,
        "vertices": 459,
        "facialGridMeshes": 8,
        "presetExpressions": 17,
        "customExpressions": 3,
        "springChains": 3,
        "springJoints": 5,
        "phaseVideos": 6,
    }
