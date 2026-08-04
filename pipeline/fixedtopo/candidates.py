"""Generate deterministic framing candidates for a fixed-topology contract."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from pipeline.fixedtopo import contract, imaging, landmarks, normalize
from pipeline.fixedtopo.palette import Palette


@dataclass(frozen=True, slots=True)
class Profile:
    """One deterministic scale variation around the calibrated fit."""

    name: str
    scale_factor: float


PROFILES = (
    Profile("compact", 0.98),
    Profile("balanced", 1.0),
    Profile("close", 1.02),
)


def _sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def _scaled_about_eyes(
    base: normalize.Similarity,
    source_eyes: tuple[normalize.Point, normalize.Point],
    target_eyes: tuple[normalize.Point, normalize.Point],
    factor: float,
) -> normalize.Similarity:
    """Change scale while keeping the eye midpoint on the contract anchor."""
    source_mid = np.asarray(source_eyes, dtype=np.float64).mean(axis=0)
    target_mid = np.asarray(target_eyes, dtype=np.float64).mean(axis=0)
    scale = base.scale * factor
    cos = scale * np.cos(base.rotation)
    sin = scale * np.sin(base.rotation)
    mapped = np.array(
        [cos * source_mid[0] - sin * source_mid[1], sin * source_mid[0] + cos * source_mid[1]]
    )
    translation = target_mid - mapped
    return normalize.Similarity(
        scale=float(scale),
        rotation=base.rotation,
        translation=(float(translation[0]), float(translation[1])),
    )


def generate(
    source: Path,
    contract_path: Path,
    palette_path: Path,
    output: Path,
) -> dict:
    """Write three normalized composites and a reproducibility manifest."""
    rgba = imaging.load_rgba(source)
    marks, _ = landmarks.detect(rgba, Palette.load(palette_path))
    fixed = contract.load(contract_path)
    source_points = [marks.eye_left, marks.eye_right, marks.mouth]
    target_points = fixed.anchor_pair(("eye_left", "eye_right", "mouth"))
    base = normalize.fit(source_points, target_points, allow_rotation=False)
    output.mkdir(parents=True, exist_ok=True)

    candidates = []
    for profile in PROFILES:
        transform = _scaled_about_eyes(
            base,
            (marks.eye_left, marks.eye_right),
            (fixed.anchors["eye_left"], fixed.anchors["eye_right"]),
            profile.scale_factor,
        )
        destination = output / f"{profile.name}.png"
        imaging.save_rgba(normalize.resample(rgba, transform, fixed.canvas), destination)
        mapped = transform.apply(source_points)
        candidates.append(
            {
                "profile": asdict(profile),
                "file": destination.name,
                "sha256": _sha256(destination),
                "transform": {
                    "scale": round(transform.scale, 8),
                    "rotation": round(transform.rotation, 8),
                    "translation": [round(item, 4) for item in transform.translation],
                },
                "anchor_residuals": [
                    round(value, 4)
                    for value in normalize.residuals(transform, source_points, target_points)
                ],
                "mapped": [[round(x, 2), round(y, 2)] for x, y in mapped],
            }
        )

    manifest = {
        "schema": "mugi-live2d/normalized-candidates@1",
        "source": source.as_posix(),
        "source_sha256": _sha256(source),
        "contract": contract_path.as_posix(),
        "contract_sha256": _sha256(contract_path),
        "palette": palette_path.as_posix(),
        "candidates": candidates,
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest
