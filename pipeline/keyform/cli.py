"""Command line entry point: ``python -m pipeline.keyform <command>``."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from pipeline.keyform import manifest as mf
from pipeline.keyform import meshmap as mm
from pipeline.keyform import transfer, verification
from pipeline.sandbox.manifest import sha256_file


def _emit(document: Any, path: Path | None) -> None:
    """Write JSON to ``path`` or to stdout."""
    rendered = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    if path is None:
        sys.stdout.write(rendered)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rendered, encoding="utf-8")


def _provenance(path: Path) -> dict[str, str]:
    """Record which file a plan came from, and exactly which bytes."""
    return {"path": str(path).replace("\\", "/"), "sha256": sha256_file(path)}


def _validate(args: argparse.Namespace) -> int:
    """Load one manifest and report what it says about itself."""
    document = mf.load(args.manifest)
    meshes: list[dict[str, Any]] = []
    problems: list[dict[str, str]] = []
    for mesh in document.meshes:
        entry: dict[str, Any] = {
            "id": mesh.id,
            "vertex_count": mesh.vertex_count,
            "triangles": len(mesh.triangles),
            "forms": len(mesh.forms),
            "parameters": list(mesh.parameters),
            "topology_digest": mf.topology_digest(mesh),
            "invariant_digest": mf.invariant_digest(mesh),
        }
        try:
            entry["reference_key"] = document.reference_form(mesh).key
        except mf.ReferenceFormError as error:
            entry["reference_key"] = None
            problems.append({"code": "reference_form", "scope": mesh.id, "message": str(error)})
        meshes.append(entry)

    report = {
        "schema": mf.MANIFEST_SCHEMA,
        "model": document.id,
        "role": document.role,
        "canvas": list(document.canvas),
        "artmesh_count": len(document.meshes),
        "keyform_count": sum(len(mesh.forms) for mesh in document.meshes),
        "parameters": len(document.parameters),
        "status": "rejected" if problems else "ready",
        "problems": problems,
        "meshes": meshes,
    }
    _emit(report, args.out)
    if args.out is not None:
        _emit({"status": report["status"], "problems": problems}, None)
    return 1 if problems else 0


def _draft_map(args: argparse.Namespace) -> int:
    """Propose a mapping from fixed topology, leaving every ambiguity to a human."""
    source, target = mf.load(args.source), mf.load(args.target)
    by_digest: dict[str, list[str]] = {}
    for mesh in source.meshes:
        by_digest.setdefault(mf.topology_digest(mesh), []).append(mesh.id)
    claims: dict[str, int] = {}
    for mesh in target.meshes:
        digest = mf.topology_digest(mesh)
        claims[digest] = claims.get(digest, 0) + 1

    pairs: list[dict[str, Any]] = []
    unassigned: list[dict[str, Any]] = []
    for mesh in target.meshes:
        digest = mf.topology_digest(mesh)
        candidates = by_digest.get(digest, [])
        if len(candidates) == 1 and claims[digest] == 1:
            pairs.append(
                {
                    "target": mesh.id,
                    "source": candidates[0],
                    "note": "one source mesh shares this topology; confirm it is the same part",
                }
            )
        else:
            unassigned.append(
                {
                    "target": mesh.id,
                    "vertex_count": mesh.vertex_count,
                    "candidates": candidates,
                }
            )

    _emit(
        {
            "schema": mm.MAP_SCHEMA,
            "id": args.id,
            "source_model": source.id,
            "target_model": target.id,
            "frame": args.frame,
            "limits": {} if args.max_displacement is None else {
                "max_displacement_px": args.max_displacement
            },
            "review": (
                "A draft. Every entry below is a proposal: confirm each pair by part, then move "
                "each unassigned target into pairs or into excluded with a written reason. "
                "'unassigned' is ignored when the map is loaded, so a draft stays rejected."
            ),
            "pairs": pairs,
            "excluded": [],
            "unassigned": unassigned,
        },
        args.out,
    )
    return 0


def _plan(args: argparse.Namespace) -> int:
    """Emit the transfer plan the Cubism bridge applies."""
    source, target = mf.load(args.source), mf.load(args.target)
    mesh_map = mm.load(args.map)
    document = transfer.plan(
        source,
        target,
        mesh_map,
        frame_mode=args.frame,
        max_displacement=args.max_displacement,
        provenance={
            "source": _provenance(args.source),
            "target": _provenance(args.target),
            "map": _provenance(args.map),
        },
    )
    _emit(document, args.out)
    if args.out is not None:
        _emit({"status": document["status"], **document["summary"]}, None)
    return 0 if document["status"] == "ready" else 1


def _verify(args: argparse.Namespace) -> int:
    """Prove that a Cubism re-export matches an approved plan."""
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    report = verification.verify(plan, mf.load(args.actual))
    _emit(report, args.out)
    if args.out is not None:
        _emit({"status": report["status"], "problems": report["problems"]}, None)
    return 0 if report["status"] == "ready" else 1


def build_parser() -> argparse.ArgumentParser:
    """Return the command line parser."""
    parser = argparse.ArgumentParser(
        prog="python -m pipeline.keyform",
        description="Plan, apply and verify keyform transfer onto target ArtMeshes.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    validate = commands.add_parser("validate", help="check one keyform manifest on its own")
    validate.add_argument("manifest", type=Path)
    validate.add_argument("--out", type=Path)
    validate.set_defaults(handler=_validate)

    draft = commands.add_parser("draft-map", help="propose a mesh mapping for human review")
    draft.add_argument("--source", type=Path, required=True)
    draft.add_argument("--target", type=Path, required=True)
    draft.add_argument("--id", default="draft", help="identifier written into the draft")
    draft.add_argument("--frame", choices=mm.FRAME_MODES, default="similarity")
    draft.add_argument("--max-displacement", type=float, help="reviewed ceiling in canvas pixels")
    draft.add_argument("--out", type=Path)
    draft.set_defaults(handler=_draft_map)

    planner = commands.add_parser("plan", help="emit a transfer plan; exit 1 when it is rejected")
    planner.add_argument("--source", type=Path, required=True)
    planner.add_argument("--target", type=Path, required=True)
    planner.add_argument(
        "--map",
        type=Path,
        required=True,
        help="reviewed source-to-target ArtMesh mapping; never selected implicitly",
    )
    planner.add_argument(
        "--frame",
        choices=mm.FRAME_MODES,
        help="override the mapping's default frame; per-pair modes still win",
    )
    planner.add_argument(
        "--max-displacement",
        type=float,
        help="reject any mesh whose transferred motion exceeds this many canvas pixels",
    )
    planner.add_argument("--out", type=Path)
    planner.set_defaults(handler=_plan)

    verifier = commands.add_parser("verify", help="verify a re-extracted Cubism document")
    verifier.add_argument("--plan", type=Path, required=True)
    verifier.add_argument("--actual", type=Path, required=True)
    verifier.add_argument("--out", type=Path)
    verifier.set_defaults(handler=_verify)

    return parser


def main(argv: list[str] | None = None) -> int:
    """Run one command and return its exit code."""
    args = build_parser().parse_args(argv)
    try:
        return int(args.handler(args))
    except (mf.ManifestError, mm.MeshMapError) as error:
        sys.stderr.write(f"{type(error).__name__}: {error}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
