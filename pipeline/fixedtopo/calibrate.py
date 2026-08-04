"""Turn a reviewed spec plus a reference drawing into a frozen contract.

The contract has to come from somewhere. Writing anchor pixels by hand is not
reviewable and not reproducible, so they are calibrated once from a reference
image: the head is scaled until the face satisfies the spec's own minimum face
size, centred horizontally, and hung from a fixed crown margin. The result is
committed and then treated as fixed for every later run.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from pipeline.fixedtopo import imaging, normalize
from pipeline.fixedtopo import landmarks as lm
from pipeline.fixedtopo.contract import CONTRACT_SCHEMA
from pipeline.fixedtopo.imaging import Box
from pipeline.fixedtopo.palette import Palette

SPEC_SCHEMA = "mugi-live2d/fixed-topology-spec@1"


def face_oval(marks: lm.Landmarks, proportions: dict[str, float]) -> Box:
    """Return the whole head-skin oval, including the forehead behind the fringe.

    The visible skin stops at the fringe, but the rig's face layer has to reach
    the top of the skull or the head cannot be turned. The oval is anchored on
    the measured cheeks and chin and sized by the spec's ratios.
    """
    x0, _, x1, _ = marks.face
    width = (x1 - x0) * proportions["face_oval_width_ratio"]
    height = (x1 - x0) * proportions["face_oval_height_ratio"]
    centre_x = (x0 + x1) / 2.0
    chin_y = marks.chin[1]
    return (
        int(round(centre_x - width / 2.0)),
        int(round(chin_y - height)),
        int(round(centre_x + width / 2.0)),
        int(round(chin_y)),
    )


def frame_transform(
    marks: lm.Landmarks, spec: dict[str, Any]
) -> tuple[normalize.Similarity, dict[str, float]]:
    """Return the calibration transform and the numbers that justified it."""
    proportions = spec["proportions"]
    canvas_width, canvas_height = spec["canvas"]["width"], spec["canvas"]["height"]
    oval = face_oval(marks, proportions)
    oval_width, oval_height = oval[2] - oval[0], oval[3] - oval[1]

    minimum = spec["minimum_bbox"]["Face"]
    needed = max(minimum["width"] / oval_width, minimum["height"] / oval_height)
    scale = needed * proportions["min_scale_margin"]

    head_width = marks.head_core[2] - marks.head_core[0]
    ceiling = canvas_width * proportions["max_head_width_ratio"] / head_width
    if scale > ceiling:
        raise ValueError(
            f"face minimum needs scale {scale:.3f} but the head only fits up to {ceiling:.3f}; "
            "the reference framing cannot satisfy this contract"
        )

    head_centre = (marks.head_core[0] + marks.head_core[2]) / 2.0
    transform = normalize.Similarity(
        scale=scale,
        rotation=0.0,
        translation=(
            canvas_width / 2.0 - scale * head_centre,
            proportions["crown_margin"] - scale * marks.crown[1],
        ),
    )
    report = {
        "scale": round(scale, 6),
        "scale_required_by_face_minimum": round(needed, 6),
        "scale_ceiling_from_head_width": round(ceiling, 6),
        "face_oval_source": list(oval),
        "face_forehead_clip_source": [
            0,
            0,
            canvas_width,
            int(
                round(
                    oval[1]
                    + (oval[3] - oval[1]) * proportions["face_forehead_height_ratio"]
                )
            ),
        ],
        "face_oval_canvas": list(transform.apply_box(oval)),
        "canvas": [canvas_width, canvas_height],
    }
    return transform, report


def _project(frame: Box, ratios: list[float]) -> Box:
    """Map ``[x0, y0, x1, y1]`` frame ratios into canvas pixels."""
    fx0, fy0, fx1, fy1 = frame
    width, height = fx1 - fx0, fy1 - fy0
    return (
        int(round(fx0 + ratios[0] * width)),
        int(round(fy0 + ratios[1] * height)),
        int(round(fx0 + ratios[2] * width)),
        int(round(fy0 + ratios[3] * height)),
    )


def _feature(entry: dict[str, Any], centre: tuple[float, float], unit: tuple[float, float]) -> Box:
    """Return a box centred on a feature, sized in that feature's own units."""
    offset = entry.get("offset", [0.0, 0.0])
    half_width = unit[0] * entry["scale"][0] / 2.0
    half_height = unit[1] * entry["scale"][1] / 2.0
    centre_x = centre[0] + offset[0] * unit[0]
    centre_y = centre[1] + offset[1] * unit[1]
    return (
        int(round(centre_x - half_width)),
        int(round(centre_y - half_height)),
        int(round(centre_x + half_width)),
        int(round(centre_y + half_height)),
    )


def build(spec: dict[str, Any], marks: lm.Landmarks, reference: dict[str, str]) -> dict[str, Any]:
    """Return a contract document calibrated against one reference drawing."""
    if spec.get("schema") != SPEC_SCHEMA:
        raise ValueError(f"unsupported spec schema: {spec.get('schema')!r}")
    transform, frame_report = frame_transform(marks, spec)
    canvas = (spec["canvas"]["width"], spec["canvas"]["height"])

    head = transform.apply_box(marks.head_core)
    chin = transform.apply([marks.chin])[0]
    torso = (
        transform.apply_box(marks.subject)[0],
        int(round(chin[1])),
        transform.apply_box(marks.subject)[2],
        canvas[1],
    )
    oval = transform.apply_box(face_oval(marks, spec["proportions"]))
    eye_left, eye_right, mouth, crown = transform.apply(
        [marks.eye_left, marks.eye_right, marks.mouth, marks.crown]
    )
    iris_unit = (
        (marks.eye_left_box[2] - marks.eye_left_box[0]) * transform.scale,
        (marks.eye_left_box[3] - marks.eye_left_box[1]) * transform.scale,
    )
    face_width = float(oval[2] - oval[0])

    regions: dict[str, dict[str, Any]] = {"Face": {"shape": "ellipse", "box": list(oval)}}
    for name, entry in spec.get("head_regions", {}).items():
        regions[name] = {
            "shape": entry.get("shape", "box"),
            "box": list(_project(head, entry["ratios"])),
        }
    for name, entry in spec.get("torso_regions", {}).items():
        regions[name] = {
            "shape": entry.get("shape", "box"),
            "box": list(_project(torso, entry["ratios"])),
        }
    for name, entry in spec.get("feature_regions", {}).items():
        centre = {"eye_left": eye_left, "eye_right": eye_right, "mouth": mouth}[entry["anchor"]]
        unit = iris_unit if entry.get("unit", "iris") == "iris" else (face_width, face_width)
        regions[name] = {
            "shape": entry.get("shape", "box"),
            "box": list(_feature(entry, centre, unit)),
        }

    document = {
        "schema": CONTRACT_SCHEMA,
        "id": spec["id"],
        "derived_from": reference,
        "calibration": frame_report,
        "canvas": spec["canvas"],
        "proportions": spec["proportions"],
        "anchors": {
            "eye_left": [round(eye_left[0], 2), round(eye_left[1], 2)],
            "eye_right": [round(eye_right[0], 2), round(eye_right[1], 2)],
            "mouth": [round(mouth[0], 2), round(mouth[1], 2)],
            "chin": [round(chin[0], 2), round(chin[1], 2)],
            "crown": [round(crown[0], 2), round(crown[1], 2)],
        },
        "frame": {"head": list(head), "torso": list(torso), "face_oval": list(oval)},
        "regions": dict(sorted(regions.items())),
    }
    for key in (
        "required_layers",
        "optional_layers",
        "draw_order",
        "clipping",
        "minimum_bbox",
        "minimum_pixels",
        "containment",
        "overlap",
        "seams",
        "envelopes",
        "islands",
    ):
        if key in spec:
            document[key] = spec[key]
    return document


def calibrate(
    spec_path: Path, reference: Path, palette_path: Path, settings: lm.DetectSettings | None = None
) -> dict[str, Any]:
    """Detect landmarks on ``reference`` and return the calibrated contract."""
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    rgba = imaging.load_rgba(reference)
    marks, _ = lm.detect(rgba, Palette.load(palette_path), settings)
    document = build(
        spec,
        marks,
        {
            "reference": Path(reference).as_posix(),
            "reference_sha256": _digest(Path(reference)),
            "palette": Path(palette_path).as_posix(),
            "spec": Path(spec_path).as_posix(),
        },
    )
    document["reference_landmarks"] = marks.to_json()
    return document


def _digest(path: Path) -> str:
    """Return a file's SHA-256 digest."""
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


__all__ = ["build", "calibrate", "face_oval", "frame_transform", "SPEC_SCHEMA"]
