"""Command line entry point: ``python -m pipeline.fixedtopo <command>``."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from pipeline.fixedtopo import calibrate as calibration
from pipeline.fixedtopo import imaging
from pipeline.fixedtopo import landmarks as lm
from pipeline.fixedtopo.palette import Palette

DEFAULT_SPEC = Path("pipeline/contract-spec.mugi-hiyori-v2.json")
DEFAULT_CONTRACT = Path("pipeline/topology.mugi-hiyori-v2.json")
DEFAULT_PALETTE = Path("pipeline/palette.mugi.json")


def _emit(document: dict[str, Any], path: Path | None) -> None:
    """Write JSON to ``path`` or to stdout."""
    rendered = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    if path is None:
        sys.stdout.write(rendered)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rendered, encoding="utf-8")


def _measure(args: argparse.Namespace) -> int:
    """Print the landmarks measured on one image."""
    rgba = imaging.load_rgba(args.image)
    marks, _ = lm.detect(rgba, Palette.load(args.palette))
    _emit(marks.to_json(), args.out)
    return 0


def _calibrate(args: argparse.Namespace) -> int:
    """Freeze a contract from the reviewed spec and a reference drawing."""
    document = calibration.calibrate(args.spec, args.reference, args.palette)
    _emit(document, args.out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Return the command line parser."""
    parser = argparse.ArgumentParser(
        prog="python -m pipeline.fixedtopo",
        description="Normalise character art onto Mugi's fixed Live2D topology.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    measure = commands.add_parser("measure", help="report the landmarks found in an image")
    measure.add_argument("image", type=Path)
    measure.add_argument("--palette", type=Path, default=DEFAULT_PALETTE)
    measure.add_argument("--out", type=Path)
    measure.set_defaults(handler=_measure)

    calibrate = commands.add_parser("calibrate", help="freeze a contract from a reference drawing")
    calibrate.add_argument("reference", type=Path)
    calibrate.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    calibrate.add_argument("--palette", type=Path, default=DEFAULT_PALETTE)
    calibrate.add_argument("--out", type=Path, default=DEFAULT_CONTRACT)
    calibrate.set_defaults(handler=_calibrate)

    return parser


def main(argv: list[str] | None = None) -> int:
    """Run one command and return its exit code."""
    args = build_parser().parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
