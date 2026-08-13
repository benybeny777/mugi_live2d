from __future__ import annotations

import argparse
import json
from pathlib import Path

from pipeline.vrm_layers import extract_layer_sprites, flatten_sprites

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PSD = ROOT / "work" / "psd" / "hiyori" / "mugi-hiyori-compatible-final-2x.psd"
DEFAULT_OUTPUT = ROOT / "temp" / "vrm-layers"


def main() -> int:
    parser = argparse.ArgumentParser(description="Export deterministic Mugi VRM layer sprites")
    parser.add_argument("--psd", type=Path, default=DEFAULT_PSD)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    canvas_size, sprites = extract_layer_sprites(args.psd.resolve())
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    manifest = {"canvas": list(canvas_size), "layers": []}
    for sprite in sprites:
        filename = f"{sprite.name}.png"
        sprite.image.save(output / filename, optimize=True)
        manifest["layers"].append(
            {
                "name": sprite.name,
                "bone": sprite.bone,
                "depth": sprite.depth,
                "canvasBox": list(sprite.canvas_box),
                "restVisible": sprite.rest_visible,
                "file": filename,
            }
        )
    flatten_sprites(canvas_size, sprites).save(output / "composite.png", optimize=True)
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"output": str(output), "layers": len(sprites)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
