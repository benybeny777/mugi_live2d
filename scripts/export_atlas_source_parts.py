"""Export full-canvas PSD composites used by the fixed Hiyori atlas remapper.

The mapping is intentionally semantic (Cubism Part ID -> PSD layer names).  The
Hiyori MOC remains the topology/rig authority; these PNGs supply only Mugi's
pixels.  Outputs are intermediate build artifacts and belong under ``temp/``.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable
from pathlib import Path

from PIL import Image
from psd_tools import PSDImage

PART_LAYERS: dict[str, tuple[str, ...]] = {
    "PartCheek": (),
    "PartBrow": ("左眉", "右眉"),
    "PartEyeBall": ("左瞳", "右瞳", "左ハイライト", "右ハイライト"),
    "PartEye": (
        "左白目",
        "右白目",
        "左まつ毛",
        "右まつ毛",
        "左瞳",
        "右瞳",
        "左ハイライト",
        "右ハイライト",
        "左まつげ1",
        "左まつげ2",
        "左まつげ3",
        "左まつげ4",
        "左まつげ5",
        "左まつげ6",
        "右まつげ1",
        "右まつげ2",
        "右まつげ3",
        "右まつげ4",
        "右まつげ5",
        "右まつげ6",
        "右まつげ7",
        "左笑い目くぼみ",
        "右笑い目くぼみ",
    ),
    "PartNose": ("鼻",),
    "PartMouth": ("唇", "上口", "下口", "口中", "口ハイライト"),
    "PartFace": ("顔下地", "顔"),
    "PartEar": ("左耳", "右耳"),
    "PartHairSide": ("前髪左", "前髪右"),
    "PartHairFront": ("前髪左", "前髪", "前髪右", "装飾"),
    "PartHairBack": ("後ろ髪", "左はね髪", "右はね髪", "アホ毛"),
    "PartNeck": ("首",),
    "PartBody": ("体",),
    "PartArmA": ("左腕", "右腕"),
    "PartBackground": (),
    "PartSketch": (),
}


def leaf_layers(layers: Iterable[object]) -> list[object]:
    result: list[object] = []
    for layer in layers:
        if layer.is_group():
            result.extend(leaf_layers(layer))
        else:
            result.append(layer)
    return result


def composite_selected(psd: PSDImage, selected_names: tuple[str, ...]) -> Image.Image:
    canvas = Image.new("RGBA", psd.size, (0, 0, 0, 0))
    selected = set(selected_names)
    # psd-tools exposes the stack from foreground to background.  Composite in
    # reverse so the original foreground ordering is retained.
    for layer in reversed(leaf_layers(psd)):
        if layer.name not in selected:
            continue
        rendered = layer.composite()
        if rendered is None:
            continue
        canvas.alpha_composite(rendered.convert("RGBA"), (layer.left, layer.top))
    return canvas


def export_parts(psd_path: Path, output: Path) -> dict[str, object]:
    psd = PSDImage.open(psd_path)
    available = {layer.name for layer in leaf_layers(psd)}
    requested = {name for names in PART_LAYERS.values() for name in names}
    missing = sorted(requested - available)
    if missing:
        raise ValueError(f"PSD is missing mapped layers: {', '.join(missing)}")

    output.mkdir(parents=True, exist_ok=True)
    files: dict[str, str] = {}
    bboxes: dict[str, list[int] | None] = {}
    for part_id, names in PART_LAYERS.items():
        image = composite_selected(psd, names)
        path = output / f"{part_id}.png"
        image.save(path, optimize=True)
        files[part_id] = path.name
        bbox = image.getchannel("A").getbbox()
        bboxes[part_id] = list(bbox) if bbox is not None else None

    manifest: dict[str, object] = {
        "schema": "mugi-live2d/atlas-source-parts@1",
        "source": str(psd_path.as_posix()),
        "canvas": {"width": psd.width, "height": psd.height},
        "parts": {
            part_id: {"file": files[part_id], "layers": list(names), "bbox": bboxes[part_id]}
            for part_id, names in PART_LAYERS.items()
        },
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("psd", type=Path)
    parser.add_argument("--output", type=Path, default=Path("temp/atlas-parts"))
    args = parser.parse_args()
    manifest = export_parts(args.psd, args.output)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
