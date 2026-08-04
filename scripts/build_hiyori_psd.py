"""Build Mugi's full-resolution Hiyori-compatible PSD from See-through masks."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter

CREATOR_REPOSITORY = Path(r"C:\00_PG\30_live")
MODEL_REPOSITORY = Path(r"C:\00_PG\40_mugi_live2d")
SOURCE = MODEL_REPOSITORY / "source" / "mugi-original.png"
SEE_THROUGH_LAYERS = MODEL_REPOSITORY / "work" / "psd" / "seethrough" / "mugi-original"
OUTPUT_DIRECTORY = MODEL_REPOSITORY / "work" / "psd" / "hiyori"

sys.path.insert(0, str(CREATOR_REPOSITORY))

from app.psd.exporter import LayerBuilder, PsdExporter  # noqa: E402
from app.segmentation.seethrough import SeeThroughSegmentationBackend  # noqa: E402

from scripts.complete_hiyori_face import complete_face_layers  # noqa: E402


def _add_hair_underlay_overlap(layers_directory: Path) -> None:
    """Add a narrow painted underlay below independently moving hair pieces.

    Cubism samples each ArtMesh independently.  Two masks that meet at an exact
    one-pixel boundary can therefore reveal the canvas as a straight seam after
    scaling or deformation.  The back-hair layer is already below the moving
    pieces, so copying only their inner edge into its alpha creates a small,
    hidden overlap without expanding the outside silhouette.
    """
    back_path = layers_directory / "HairBack.png"
    with Image.open(back_path) as opened:
        back = opened.convert("RGBA")
    back_alpha = back.getchannel("A")
    overlap_sources = (
        "HairFront.png",
        "HairSideL.png",
        "HairSideR.png",
        "HairTipL.png",
        "HairTipR.png",
        "HairAhoge.png",
    )
    for filename in overlap_sources:
        with Image.open(layers_directory / filename) as opened:
            alpha = opened.getchannel("A")
        eroded = alpha.filter(ImageFilter.MinFilter(11))
        inner_edge = ImageChops.subtract(alpha, eroded)
        back_alpha = ImageChops.lighter(back_alpha, inner_edge)
    back.putalpha(back_alpha)
    back.save(back_path)


def main() -> int:
    """Generate editable masks, PNG layers, and a Cubism-ready PSD."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    masks = SeeThroughSegmentationBackend(SEE_THROUGH_LAYERS).segment(
        SOURCE, OUTPUT_DIRECTORY / "masks"
    )
    layers = LayerBuilder().build(SOURCE, masks, OUTPUT_DIRECTORY / "layers")
    complete_face_layers(SOURCE, OUTPUT_DIRECTORY / "layers")
    _add_hair_underlay_overlap(OUTPUT_DIRECTORY / "layers")
    destination = OUTPUT_DIRECTORY / "mugi-hiyori-compatible-final.psd"
    PsdExporter().export(layers, destination)
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
