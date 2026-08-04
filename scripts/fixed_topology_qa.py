"""Validate replacement art against Mugi's fixed Hiyori-grade topology."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops


def alpha(path: Path, canvas: tuple[int, int]) -> Image.Image:
    with Image.open(path) as opened:
        if opened.size != canvas:
            raise ValueError(f"canvas {opened.size[0]}x{opened.size[1]} != {canvas[0]}x{canvas[1]}")
        return opened.convert("RGBA").getchannel("A")


def pixels(mask: Image.Image) -> int:
    return sum(mask.histogram()[1:])


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def validate(layers: Path, topology_path: Path) -> dict[str, Any]:
    topology = json.loads(topology_path.read_text(encoding="utf-8"))
    canvas = (topology["canvas"]["width"], topology["canvas"]["height"])
    failures: list[str] = []
    warnings: list[str] = []
    masks: dict[str, Image.Image] = {}
    records: dict[str, Any] = {}

    for name in topology["required_layers"] + topology["optional_layers"]:
        path = layers / f"{name}.png"
        if not path.exists():
            if name in topology["required_layers"]:
                failures.append(f"missing required layer: {name}")
            continue
        try:
            mask = alpha(path, canvas)
        except ValueError as error:
            failures.append(f"{name}: {error}")
            continue
        count = pixels(mask)
        bbox = mask.getbbox()
        if count == 0 or bbox is None:
            failures.append(f"empty layer: {name}")
            continue
        masks[name] = mask
        records[name] = {"file": path.name, "sha256": digest(path), "alpha_pixels": count, "bbox": list(bbox)}

    for name, limits in topology.get("minimum_bbox", {}).items():
        if name not in records:
            continue
        x0, y0, x1, y1 = records[name]["bbox"]
        width, height = x1 - x0, y1 - y0
        if width < limits["width"] or height < limits["height"]:
            failures.append(f"{name}: bbox {width}x{height} below {limits['width']}x{limits['height']}")

    for rule in topology.get("containment", []):
        inner, outer = masks.get(rule["inner"]), masks.get(rule["outer"])
        if inner is None or outer is None:
            continue
        inside = pixels(ImageChops.multiply(inner, outer))
        ratio = inside / max(1, pixels(inner))
        if ratio < rule["min_ratio"]:
            failures.append(f"{rule['inner']} containment in {rule['outer']}: {ratio:.3f} < {rule['min_ratio']:.3f}")

    for rule in topology.get("overlap", []):
        left, right = masks.get(rule["a"]), masks.get(rule["b"])
        if left is None or right is None:
            continue
        overlap = pixels(ImageChops.multiply(left, right))
        if overlap < rule["min_pixels"]:
            failures.append(f"{rule['a']}/{rule['b']} overlap: {overlap} < {rule['min_pixels']}")

    known = {f"{name}.png" for name in topology["required_layers"] + topology["optional_layers"]}
    extra = sorted(path.name for path in layers.glob("*.png") if path.name not in known)
    if extra:
        warnings.append("uncontracted layers: " + ", ".join(extra))
    return {
        "schema": "mugi-live2d/fixed-topology-report@1",
        "topology": topology["id"],
        "canvas": {"width": canvas[0], "height": canvas[1]},
        "passed": not failures,
        "failures": failures,
        "warnings": warnings,
        "layers": records,
    }


def write_html(report: dict[str, Any], path: Path) -> None:
    rows = "".join(
        f"<tr><td>{html.escape(name)}</td><td>{value['alpha_pixels']}</td><td>{' × '.join(map(str, value['bbox']))}</td></tr>"
        for name, value in sorted(report["layers"].items())
    )
    issues = "".join(f"<li>{html.escape(item)}</li>" for item in report["failures"] + report["warnings"])
    status = "PASS" if report["passed"] else "FAIL"
    path.write_text(
        "<!doctype html><meta charset=utf-8><title>Fixed topology QA</title>"
        "<style>body{font:16px system-ui;max-width:960px;margin:40px auto}table{border-collapse:collapse;width:100%}"
        "td,th{border:1px solid #bbb;padding:6px;text-align:left}.PASS{color:#187a32}.FAIL{color:#b42318}</style>"
        f"<h1 class={status}>{status}: {html.escape(report['topology'])}</h1><ul>{issues}</ul>"
        f"<table><tr><th>Layer</th><th>Alpha pixels</th><th>Bounding box</th></tr>{rows}</table>",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("layers", type=Path)
    parser.add_argument("--topology", type=Path, default=Path("pipeline/topology.mugi-hiyori-v1.json"))
    parser.add_argument("--json", type=Path)
    parser.add_argument("--html", type=Path)
    args = parser.parse_args()
    report = validate(args.layers, args.topology)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    if args.html:
        args.html.parent.mkdir(parents=True, exist_ok=True)
        write_html(report, args.html)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
