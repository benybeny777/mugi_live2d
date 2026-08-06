from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageStat

ROOT = Path(__file__).resolve().parents[1]


def _load_vrm_validator():
    path = ROOT / "scripts" / "validate_vrm.py"
    spec = importlib.util.spec_from_file_location("validate_vrm_visual_model", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load validate_vrm.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _foreground_bbox(frame: Image.Image) -> tuple[int, int, int, int] | None:
    rgb = frame.convert("RGB")
    background = Image.new("RGB", rgb.size, rgb.getpixel((0, 0)))
    mask = ImageChops.difference(rgb, background).convert("L").point(
        lambda value: 255 if value > 12 else 0
    )
    return mask.getbbox()


def validate_visual(root: Path = ROOT) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    gif_path = root / "docs" / "media" / "mugi-vrm-preview.gif"
    if not gif_path.is_file():
        return ["latest VRM GIF is missing"], {}

    frames: list[Image.Image] = []
    with Image.open(gif_path) as gif:
        frame_count = getattr(gif, "n_frames", 1)
        sample_indices = sorted(
            {round((frame_count - 1) * fraction) for fraction in (0, 0.25, 0.5, 0.75, 1)}
        )
        for index in sample_indices:
            gif.seek(index)
            frames.append(gif.convert("RGB"))
        size = gif.size

    motion_scores = [
        sum(ImageStat.Stat(ImageChops.difference(frames[0], frame)).mean) / 3
        for frame in frames[1:]
    ]
    foot_top = round(size[1] * 0.72)
    boxes = [
        _foreground_bbox(frame.crop((0, foot_top, size[0], size[1]))) for frame in frames
    ]
    bottom_centres = [
        (box[0] + box[2]) / 2 for box in boxes if box is not None
    ]

    if size != (940, 720):
        errors.append("latest VRM GIF must be 940x720")
    if frame_count < 80:
        errors.append("latest VRM GIF must contain at least 80 frames")
    if not motion_scores or max(motion_scores) < 0.15:
        errors.append("latest VRM GIF does not show enough visible motion")
    if len(bottom_centres) != len(frames):
        errors.append("character feet are not visible in every sampled frame")
    elif max(bottom_centres) - min(bottom_centres) > 3.0:
        errors.append("character foot position drifts by more than 3 pixels")

    validator = _load_vrm_validator()
    document, _ = validator.read_glb(root / "exports" / "vrm" / "mugi.vrm")
    mesh_names = {mesh.get("name") for mesh in document.get("meshes", [])}
    arm_names = {
        "screen_left_upper_armMesh",
        "screen_left_forearmMesh",
        "screen_left_handMesh",
        "screen_right_upper_armMesh",
        "screen_right_forearmMesh",
        "screen_right_handMesh",
    }
    brow_names = {"left_browMesh", "right_browMesh"}
    if not arm_names.issubset(mesh_names):
        errors.append("VRM does not contain all six arm segment meshes")
    if not brow_names.issubset(mesh_names):
        errors.append("VRM does not contain both eyebrow meshes")

    metrics = {
        "size": list(size),
        "frames": frame_count,
        "maxMotionScore": round(max(motion_scores, default=0.0), 3),
        "footDriftPx": round(
            max(bottom_centres) - min(bottom_centres) if bottom_centres else 0.0, 3
        ),
        "armSegments": len(arm_names & mesh_names),
        "browMeshes": len(brow_names & mesh_names),
    }
    return errors, metrics


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the latest Mugi VRM preview")
    parser.parse_args()
    errors, metrics = validate_visual()
    print(json.dumps({"metrics": metrics, "errors": errors}, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
