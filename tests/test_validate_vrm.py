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

    result = builder.build_vrm(ROOT / "source" / "mugi-original.png", output, 256)

    assert result["texture"][1] == 256
    assert result["cardMeters"][1] == 1.8
    assert validator.validate(output) == []


def test_validator_rejects_non_glb(tmp_path: Path) -> None:
    validator = _load_script("validate_vrm")
    invalid = tmp_path / "invalid.vrm"
    invalid.write_bytes(b"not a vrm")

    assert validator.validate(invalid) == ["file is too short to be a GLB"]
