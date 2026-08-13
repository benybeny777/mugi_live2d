from __future__ import annotations

import argparse
import json
from pathlib import Path

from pipeline.tpose_vrm_layers import extract_tpose_sprites
from pipeline.vrm_layers import flatten_sprites
from pipeline.vrm_model import build_layered_vrm_from_sprites

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = (
    ROOT / "work" / "psd" / "tpose" / "mugi-tpose-source-v1-photoshop-pd2-preview.png"
)
DEFAULT_OUTPUT = ROOT / "exports" / "vrm" / "mugi.vrm"


def main() -> int:
    """Build the production Mugi VRM from the approved same-source T-pose art."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--parts", type=Path, default=ROOT / "temp" / "tpose-vrm-parts")
    parser.add_argument("--max-texture-size", type=int, default=4096)
    args = parser.parse_args()

    canvas_size, sprites = extract_tpose_sprites(args.source)
    args.parts.mkdir(parents=True, exist_ok=True)
    for sprite in sprites:
        sprite.image.save(args.parts / f"{sprite.name}.png")
    flatten_sprites(canvas_size, sprites).save(args.parts / "composite.png")
    result = build_layered_vrm_from_sprites(
        canvas_size, sprites, args.output, args.max_texture_size
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
