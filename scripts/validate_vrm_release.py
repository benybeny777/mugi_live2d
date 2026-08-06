from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def _load_validator():
    path = ROOT / "scripts" / "validate_vrm.py"
    spec = importlib.util.spec_from_file_location("validate_vrm", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load validate_vrm.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_release(root: Path = ROOT) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    vrm_path = root / "exports" / "vrm" / "mugi.vrm"
    validator = _load_validator()
    errors.extend(validator.validate(vrm_path))
    document, _ = validator.read_glb(vrm_path)

    meshes = document.get("meshes", [])
    accessors = document.get("accessors", [])
    vertices = sum(
        accessors[primitive["attributes"]["POSITION"]]["count"]
        for mesh in meshes
        for primitive in mesh.get("primitives", [])
    )
    facial_grids = sum(
        mesh.get("extras", {}).get("grid") in ([4, 2], [5, 2]) for mesh in meshes
    )
    mesh_names = {mesh.get("name") for mesh in meshes}
    vrm = document["extensions"]["VRMC_vrm"]
    spring_bone = document["extensions"].get("VRMC_springBone", {})
    springs = spring_bone.get("springs", [])
    spring_joints = sum(max(0, len(spring.get("joints", [])) - 1) for spring in springs)
    metrics = {
        "bytes": vrm_path.stat().st_size,
        "meshes": len(meshes),
        "vertices": vertices,
        "facialGridMeshes": facial_grids,
        "presetExpressions": len(vrm.get("expressions", {}).get("preset", {})),
        "customExpressions": len(vrm.get("expressions", {}).get("custom", {})),
        "springChains": len(springs),
        "springJoints": spring_joints,
        "latestPreviews": 2,
        "armSegments": sum(
            name in mesh_names
            for name in {
                "screen_left_upper_armMesh",
                "screen_left_forearmMesh",
                "screen_left_handMesh",
                "screen_right_upper_armMesh",
                "screen_right_forearmMesh",
                "screen_right_handMesh",
            }
        ),
        "browMeshes": sum(
            name in mesh_names for name in {"left_browMesh", "right_browMesh"}
        ),
    }
    expected = {
        "meshes": 26,
        "vertices": 543,
        "facialGridMeshes": 12,
        "presetExpressions": 17,
        "customExpressions": 5,
        "springChains": 3,
        "springJoints": 5,
        "latestPreviews": 2,
        "armSegments": 6,
        "browMeshes": 2,
    }
    for name, value in expected.items():
        if metrics[name] != value:
            errors.append(f"quality metric {name}: expected {value}, got {metrics[name]}")
    if metrics["bytes"] > 10 * 1024 * 1024:
        errors.append("VRM exceeds the 10 MiB A-plan release budget")

    readme = (root / "README.md").read_text(encoding="utf-8")
    for name in ("mugi-vrm-preview.gif", "mugi-vrm-preview.mp4"):
        path = root / "docs" / "media" / name
        if not path.is_file() or path.stat().st_size == 0:
            errors.append(f"missing main VRM preview: {path.relative_to(root)}")
        if f"docs/media/{name}" not in readme:
            errors.append(f"README does not link main VRM preview: {name}")
    gif_path = root / "docs" / "media" / "mugi-vrm-preview.gif"
    if gif_path.is_file():
        with Image.open(gif_path) as gif:
            if (gif.width, gif.height) != (940, 720):
                errors.append("main VRM GIF must be 940x720")
    mp4_path = root / "docs" / "media" / "mugi-vrm-preview.mp4"
    if mp4_path.is_file() and mp4_path.read_bytes()[4:8] != b"ftyp":
        errors.append("main VRM MP4 has no ISO BMFF ftyp box")
    if "vrm-phase" in readme:
        errors.append("README must show only the latest VRM preview")
    if list((root / "docs" / "media").glob("vrm-phase*")):
        errors.append("obsolete VRM phase preview files must be removed")

    timeline = json.loads(
        (root / "vrm-viewer" / "motions" / "mugi-timeline.json").read_text(
            encoding="utf-8"
        )
    )
    if [segment["name"] for segment in timeline["segments"]] != ["idle", "greet", "talk"]:
        errors.append("motion timeline must contain idle, greet, talk in order")
    return errors, metrics


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the complete Mugi VRM release")
    parser.parse_args()
    errors, metrics = validate_release()
    print(json.dumps({"metrics": metrics, "errors": errors}, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
