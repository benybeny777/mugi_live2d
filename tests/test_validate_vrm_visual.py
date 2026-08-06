from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_visual_validator():
    path = ROOT / "scripts" / "validate_vrm_visual.py"
    spec = importlib.util.spec_from_file_location("validate_vrm_visual", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_latest_vrm_preview_visual_gate() -> None:
    validator = _load_visual_validator()

    errors, metrics = validator.validate_visual(ROOT)

    assert errors == []
    assert metrics["size"] == [940, 720]
    assert metrics["frames"] >= 80
    assert metrics["maxMotionScore"] >= 0.15
    assert metrics["footDriftPx"] <= 3.0
    assert metrics["armSegments"] == 6
    assert metrics["browMeshes"] == 2
