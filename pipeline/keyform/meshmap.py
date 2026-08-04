"""Which source ArtMesh drives which target ArtMesh, and which targets are left alone.

The mapping is reviewed data, like the fixed-topology contract: it is the record
of a human deciding that Hiyori's mesh X really is the same part as Mugi's mesh Y.
Nothing infers it at plan time. A target that is neither mapped nor explicitly
excluded is an unfinished mapping, and the planner rejects the run rather than
silently leaving that ArtMesh undeformed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

MAP_SCHEMA = "mugi-live2d/keyform-map@1"
FRAME_MODES = ("similarity", "affine")


class MeshMapError(ValueError):
    """Raised when a mesh mapping cannot be trusted as written."""


@dataclass(frozen=True, slots=True)
class Pair:
    """One reviewed source-to-target correspondence."""

    target: str
    source: str
    frame: str | None = None
    note: str = ""


@dataclass(frozen=True, slots=True)
class Excluded:
    """A target ArtMesh that is intentionally not driven by the source rig."""

    target: str
    reason: str


@dataclass(frozen=True, slots=True)
class MeshMap:
    """A parsed mesh mapping document."""

    id: str
    source_model: str
    target_model: str
    frame: str
    pairs: tuple[Pair, ...]
    excluded: tuple[Excluded, ...]
    limits: dict[str, float] = field(default_factory=dict)
    raw: dict[str, Any] = field(repr=False, default_factory=dict)

    @property
    def targets(self) -> frozenset[str]:
        """Return every target mentioned by the document."""
        return frozenset(pair.target for pair in self.pairs) | frozenset(
            entry.target for entry in self.excluded
        )

    def frame_for(self, pair: Pair) -> str:
        """Return the frame mode to use for one pair."""
        return pair.frame or self.frame

    @property
    def max_displacement(self) -> float | None:
        """Return the reviewed ceiling on transferred motion, in canvas pixels."""
        value = self.limits.get("max_displacement_px")
        return None if value is None else float(value)


def parse(data: dict[str, Any]) -> MeshMap:
    """Validate and convert an already-decoded mapping document."""
    schema = data.get("schema")
    if schema != MAP_SCHEMA:
        raise MeshMapError(f"unsupported mesh map schema: {schema!r}; expected {MAP_SCHEMA!r}")

    frame = str(data.get("frame", "similarity"))
    if frame not in FRAME_MODES:
        raise MeshMapError(f"frame must be one of {FRAME_MODES}, got {frame!r}")

    pairs: list[Pair] = []
    for index, entry in enumerate(data.get("pairs", [])):
        where = f"pairs[{index}]"
        target = str(entry.get("target", "")).strip()
        source = str(entry.get("source", "")).strip()
        if not target or not source:
            raise MeshMapError(f"{where}: a pair needs both a target and a source ArtMesh id")
        pair_frame = entry.get("frame")
        if pair_frame is not None and pair_frame not in FRAME_MODES:
            raise MeshMapError(f"{where}: frame must be one of {FRAME_MODES}, got {pair_frame!r}")
        pairs.append(
            Pair(
                target=target,
                source=source,
                frame=None if pair_frame is None else str(pair_frame),
                note=str(entry.get("note", "")),
            )
        )

    excluded: list[Excluded] = []
    for index, entry in enumerate(data.get("excluded", [])):
        where = f"excluded[{index}]"
        target = str(entry.get("target", "")).strip()
        reason = str(entry.get("reason", "")).strip()
        if not target:
            raise MeshMapError(f"{where}: an exclusion needs a target ArtMesh id")
        if not reason:
            raise MeshMapError(f"{where}: exclusion of {target!r} needs a written reason")
        excluded.append(Excluded(target=target, reason=reason))

    claimed: dict[str, str] = {}
    for pair in pairs:
        if pair.target in claimed:
            raise MeshMapError(f"target {pair.target!r} is mapped more than once")
        claimed[pair.target] = pair.source
    for entry in excluded:
        if entry.target in claimed:
            raise MeshMapError(f"target {entry.target!r} is both mapped and excluded")
        claimed[entry.target] = ""

    used: dict[str, str] = {}
    for pair in pairs:
        if pair.source in used:
            raise MeshMapError(
                f"source {pair.source!r} drives both {used[pair.source]!r} and {pair.target!r}; "
                "one source mesh cannot be two parts"
            )
        used[pair.source] = pair.target

    limits = {key: float(value) for key, value in data.get("limits", {}).items()}
    if limits.get("max_displacement_px", 1.0) <= 0.0:
        raise MeshMapError("limits.max_displacement_px must be positive when set")

    return MeshMap(
        id=str(data.get("id", "")).strip() or "unnamed",
        source_model=str(data.get("source_model", "")),
        target_model=str(data.get("target_model", "")),
        frame=frame,
        pairs=tuple(pairs),
        excluded=tuple(excluded),
        limits=limits,
        raw=data,
    )


def load(path: Path | str) -> MeshMap:
    """Read and validate a mapping document from disk."""
    return parse(json.loads(Path(path).read_text(encoding="utf-8")))
