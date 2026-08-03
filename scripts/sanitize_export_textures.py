"""Clear hidden RGB from fully transparent exported texture pixels."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image


def sanitize_texture(path: Path) -> int:
    """Set RGB to zero where alpha is zero and return the changed pixel count."""
    image = Image.open(path).convert("RGBA")
    pixels = np.array(image)
    transparent = pixels[:, :, 3] == 0
    changed = transparent & np.any(pixels[:, :, :3] != 0, axis=2)
    pixels[transparent, :3] = 0
    Image.fromarray(pixels, "RGBA").save(path, optimize=True)
    return int(changed.sum())


def main() -> int:
    """Sanitize every PNG below the supplied SDK export directories."""
    parser = argparse.ArgumentParser()
    parser.add_argument("directories", nargs="+", type=Path)
    args = parser.parse_args()
    for directory in args.directories:
        for path in sorted(directory.rglob("*.png")):
            print(f"{path}: cleared={sanitize_texture(path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
