"""Command line entry point: ``python -m pipeline.sandbox <command>``."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from pipeline.fixedtopo import imaging
from pipeline.sandbox import export as exporter
from pipeline.sandbox import manifest as mf
from pipeline.sandbox import psdlayer
from pipeline.sandbox import qa as checks
from pipeline.sandbox import restore as restorer

DEFAULT_PSD = Path("work/psd/hiyori/mugi-hiyori-compatible-clean.psd")


def _emit(document: Any, path: Path | None) -> None:
    """Write JSON to ``path`` or to stdout."""
    rendered = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    if path is None:
        sys.stdout.write(rendered)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rendered, encoding="utf-8")


def _box(text: str | None) -> tuple[int, int, int, int] | None:
    """Parse an ``x0,y0,x1,y1`` argument."""
    if not text:
        return None
    parts = [int(value) for value in text.split(",")]
    if len(parts) != 4 or parts[0] >= parts[2] or parts[1] >= parts[3]:
        raise argparse.ArgumentTypeError("expected x0,y0,x1,y1 with x0<x1 and y0<y1")
    return parts[0], parts[1], parts[2], parts[3]


def _list(args: argparse.Namespace) -> int:
    """Print every pixel layer in a PSD."""
    document = psdlayer.open_document(args.psd)
    _emit(
        {
            "psd": str(args.psd).replace("\\", "/"),
            "canvas": [int(document.width), int(document.height)],
            "layers": psdlayer.describe(document),
        },
        args.out,
    )
    return 0


def _extract(args: argparse.Namespace) -> int:
    """Write one layer as a canvas-sized transparent PNG."""
    rgba, canvas = psdlayer.extract_from_file(args.psd, args.layer, args.apply_opacity)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    imaging.save_rgba(rgba, args.out)
    box = imaging.bbox(rgba[..., 3] > 0)
    _emit(
        {
            "psd": str(args.psd).replace("\\", "/"),
            "layer": args.layer,
            "canvas": list(canvas),
            "out": str(args.out).replace("\\", "/"),
            "sha256": mf.sha256_file(args.out),
            "alpha_bbox": list(box) if box else None,
            "opaque_pixels": int((rgba[..., 3] > 0).sum()),
        },
        None,
    )
    return 0


def _export(args: argparse.Namespace) -> int:
    """Write the Photoshop sandbox for one layer."""
    document = exporter.export(
        args.psd,
        args.layer,
        args.out,
        identifier=args.id,
        grow=args.grow,
        seam=args.seam,
        margin=args.margin,
        target=args.target,
    )
    _emit(document, None)
    return 0


def _qa(args: argparse.Namespace) -> int:
    """Check a returned image without writing anything."""
    manifest = mf.load(args.sandbox / "manifest.json")
    filled = args.filled or args.sandbox / manifest.ret["file"]
    report = checks.evaluate(manifest, args.sandbox, filled)
    _emit(report, args.json)
    if args.json is not None:
        _emit(report, None)
    return 0 if report["status"] == "review_required" else 1


def _import(args: argparse.Namespace) -> int:
    """Place a reviewed result back onto the master canvas."""
    manifest = mf.load(args.sandbox / "manifest.json")
    filled = args.filled or args.sandbox / manifest.ret["file"]
    report = restorer.restore(args.sandbox, filled, args.out, args.reviewed_by, args.psd)
    _emit(report, args.json)
    if args.json is not None:
        _emit(report, None)
    if report["failed"]:
        return 1
    return 0 if report["status"] == "approved" else 2


def build_parser() -> argparse.ArgumentParser:
    """Return the command line parser."""
    parser = argparse.ArgumentParser(
        prog="python -m pipeline.sandbox",
        description="Extract PSD layers, hand a bounded crop to Photoshop, and check what returns.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    listing = commands.add_parser("list", help="print every pixel layer in a PSD")
    listing.add_argument("--psd", type=Path, default=DEFAULT_PSD)
    listing.add_argument("--out", type=Path)
    listing.set_defaults(handler=_list)

    extract = commands.add_parser("extract", help="write one layer as a transparent PNG")
    extract.add_argument("layer", help="full path such as /顔/顔, or a unique layer name")
    extract.add_argument("--psd", type=Path, default=DEFAULT_PSD)
    extract.add_argument("--out", type=Path, required=True)
    extract.add_argument(
        "--apply-opacity",
        action="store_true",
        help="multiply by the layer's opacity; off by default so parked layers still export",
    )
    extract.set_defaults(handler=_extract)

    export = commands.add_parser("export", help="write a Photoshop sandbox for one layer")
    export.add_argument("layer")
    export.add_argument("--psd", type=Path, default=DEFAULT_PSD)
    export.add_argument("--out", type=Path, required=True, help="directory to hold the sandbox")
    export.add_argument("--id", help="sandbox directory name; defaults to the layer path")
    export.add_argument("--grow", type=float, default=24.0, help="editable ring in pixels")
    export.add_argument("--seam", type=float, default=2.0, help="unlocked ring at the alpha edge")
    export.add_argument("--margin", type=int, default=32, help="context kept around the crop")
    export.add_argument("--target", type=_box, help="extra editable box as x0,y0,x1,y1 on canvas")
    export.set_defaults(handler=_export)

    qa = commands.add_parser("qa", help="check a returned image; never reports acceptance")
    qa.add_argument("sandbox", type=Path)
    qa.add_argument("--filled", type=Path)
    qa.add_argument("--json", type=Path)
    qa.set_defaults(handler=_qa)

    importer = commands.add_parser("import", help="place a reviewed result back on the canvas")
    importer.add_argument("sandbox", type=Path)
    importer.add_argument("--filled", type=Path)
    importer.add_argument("--out", type=Path, required=True)
    importer.add_argument("--psd", type=Path)
    importer.add_argument("--reviewed-by", help="name of the person who approved the image")
    importer.add_argument("--json", type=Path)
    importer.set_defaults(handler=_import)

    return parser


def main(argv: list[str] | None = None) -> int:
    """Run one command and return its exit code."""
    args = build_parser().parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
