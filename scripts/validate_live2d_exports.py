"""Validate the reproducible SDK 5/4 Mugi Live2D exports.

The checks deliberately operate on exported files, rather than screenshots or
Cubism UI state.  This makes the release gate usable after every future export.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

EXPECTED_PHYSICS: dict[str, dict[str, Any]] = {
    "後ろ髪": {
        "output": "ParamHairBack",
        "weights": [60, 60, 40, 40],
        "length": 15.0,
        "mobility": 0.95,
        "delay": 0.8,
        "acceleration": 1.5,
        "scale": 2.132,
    },
    "横髪": {
        "output": "ParamHairSide",
        "weights": [60, 60, 40, 40],
        "length": 8.0,
        "mobility": 0.95,
        "delay": 0.85,
        "acceleration": 1.5,
        "scale": 1.8,
    },
    "前髪": {
        "output": "ParamHairFront",
        "weights": [60, 60, 40, 40],
        "length": 3.0,
        "mobility": 0.95,
        "delay": 0.9,
        "acceleration": 1.5,
        "scale": 1.522,
    },
    "アホ毛": {
        "output": "ParamHairAhoge",
        "weights": [70, 70, 30, 30],
        "length": 5.0,
        "mobility": 1.0,
        "delay": 0.5,
        "acceleration": 2.0,
        "scale": 3.0,
    },
}


@dataclass(frozen=True)
class TextureMetric:
    path: str
    width: int
    height: int
    alpha_percent: float
    nonzero_alpha_pixels: int
    hidden_rgb_pixels: int


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def close(actual: float, expected: float) -> bool:
    return math.isclose(float(actual), float(expected), rel_tol=0, abs_tol=1e-6)


def texture_metric(path: Path, root: Path) -> TextureMetric:
    pixels = np.asarray(Image.open(path).convert("RGBA"))
    alpha = pixels[:, :, 3]
    hidden_rgb = (alpha == 0) & np.any(pixels[:, :, :3] != 0, axis=2)
    return TextureMetric(
        path=path.relative_to(root).as_posix(),
        width=int(pixels.shape[1]),
        height=int(pixels.shape[0]),
        alpha_percent=round(float(alpha.mean() / 255 * 100), 6),
        nonzero_alpha_pixels=int(np.count_nonzero(alpha)),
        hidden_rgb_pixels=int(np.count_nonzero(hidden_rgb)),
    )


def validate_physics(data: dict[str, Any], errors: list[str], sdk: str) -> None:
    dictionary = {item["Id"]: item["Name"] for item in data["Meta"]["PhysicsDictionary"]}
    settings = {dictionary[item["Id"]]: item for item in data["PhysicsSettings"]}
    if set(settings) != set(EXPECTED_PHYSICS):
        errors.append(f"{sdk}: physics groups are {sorted(settings)}, expected 4 named groups")
        return
    for name, expected in EXPECTED_PHYSICS.items():
        item = settings[name]
        vertex = item["Vertices"][1]
        output = item["Output"][0]
        weights = [entry["Weight"] for entry in item["Input"]]
        actual = {
            "output": output["Destination"]["Id"],
            "weights": weights,
            "length": vertex["Radius"],
            "mobility": vertex["Mobility"],
            "delay": vertex["Delay"],
            "acceleration": vertex["Acceleration"],
            "scale": output["Scale"],
        }
        for key, wanted in expected.items():
            got = actual[key]
            valid = got == wanted if isinstance(wanted, (str, list)) else close(got, wanted)
            if not valid:
                errors.append(f"{sdk}/{name}: {key}={got!r}, expected {wanted!r}")


def validate_sdk(root: Path, sdk: str, min_alpha_sum: float) -> dict[str, Any]:
    directory = root / "exports" / sdk / "mugi"
    errors: list[str] = []
    model_path = directory / "mugi.model3.json"
    physics_path = directory / "mugi.physics3.json"
    moc_path = directory / "mugi.moc3"
    for path in (model_path, physics_path, moc_path, directory / "mugi.cdi3.json"):
        if not path.is_file() or path.stat().st_size == 0:
            errors.append(f"{sdk}: missing or empty {path.name}")
    if errors:
        return {"sdk": sdk, "errors": errors, "textures": []}

    model = load_json(model_path)
    references = model.get("FileReferences", {})
    texture_paths = [directory / item for item in references.get("Textures", [])]
    metrics = [texture_metric(path, root) for path in texture_paths if path.is_file()]
    if len(metrics) != len(texture_paths):
        errors.append(f"{sdk}: a model3.json texture reference is missing")
    if len(metrics) != 3:
        errors.append(f"{sdk}: expected 3 texture sheets, got {len(metrics)}")
    for metric in metrics:
        if (metric.width, metric.height) != (4096, 4096):
            errors.append(f"{sdk}: {metric.path} is not 4096x4096")
        if metric.nonzero_alpha_pixels == 0:
            errors.append(f"{sdk}: {metric.path} is empty")
        if metric.hidden_rgb_pixels:
            errors.append(f"{sdk}: {metric.path} has {metric.hidden_rgb_pixels} hidden RGB pixels")
    alpha_sum = round(sum(item.alpha_percent for item in metrics), 6)
    if alpha_sum < min_alpha_sum:
        errors.append(f"{sdk}: summed alpha occupancy {alpha_sum}% < {min_alpha_sum}%")

    groups = {item.get("Name"): item.get("Ids") for item in model.get("Groups", [])}
    if groups.get("EyeBlink") != ["ParamEyeLOpen", "ParamEyeROpen"]:
        errors.append(f"{sdk}: EyeBlink group is missing or invalid")
    if groups.get("LipSync") != ["ParamMouthOpenY"]:
        errors.append(f"{sdk}: LipSync group is missing or invalid")

    physics = load_json(physics_path)
    validate_physics(physics, errors, sdk)
    return {
        "sdk": sdk,
        "errors": errors,
        "summed_alpha_percent": alpha_sum,
        "textures": [asdict(item) for item in metrics],
        "physics_groups": [item["Name"] for item in physics["Meta"]["PhysicsDictionary"]],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--min-alpha-sum", type=float, default=15.0)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    results = [validate_sdk(root, sdk, args.min_alpha_sum) for sdk in ("sdk5", "sdk4")]
    errors = [error for result in results for error in result["errors"]]
    report = {"ok": not errors, "results": results, "errors": errors}
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    print(rendered)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered + "\n", encoding="utf-8")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
