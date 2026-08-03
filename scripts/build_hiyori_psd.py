"""Build Mugi's full-resolution Hiyori-compatible PSD from See-through masks."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

CREATOR_REPOSITORY = Path(r"C:\00_PG\30_live")
MODEL_REPOSITORY = Path(r"C:\00_PG\40_mugi_live2d")
SOURCE = MODEL_REPOSITORY / "source" / "mugi-original.png"
SEE_THROUGH_LAYERS = (
    MODEL_REPOSITORY / "work" / "psd" / "seethrough" / "mugi-original"
)
OUTPUT_DIRECTORY = MODEL_REPOSITORY / "work" / "psd" / "hiyori"

sys.path.insert(0, str(CREATOR_REPOSITORY))

from app.psd.exporter import LayerBuilder, PsdExporter  # noqa: E402
from app.segmentation.seethrough import SeeThroughSegmentationBackend  # noqa: E402


def main() -> int:
    """Generate editable masks, PNG layers, and a Cubism-ready PSD."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    masks = SeeThroughSegmentationBackend(SEE_THROUGH_LAYERS).segment(
        SOURCE, OUTPUT_DIRECTORY / "masks"
    )
    layers = LayerBuilder().build(SOURCE, masks, OUTPUT_DIRECTORY / "layers")
    destination = OUTPUT_DIRECTORY / "mugi-hiyori-compatible-final.psd"
    PsdExporter().export(layers, destination)
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
