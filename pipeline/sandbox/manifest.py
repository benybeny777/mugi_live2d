"""The sandbox contract: what Photoshop is allowed to change, and where it goes.

A manifest is written by ``export`` and read back by ``import`` and ``qa``. It
is the only thing carried between the non-GUI side and the GUI side, so it
records the source document, the exact crop handed over, the pixels that must
survive untouched, and a SHA-256 for every file. Reruns of ``export`` with the
same inputs produce a byte-identical manifest, which is why no timestamp is
stored here.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MANIFEST_SCHEMA = "mugi-live2d/sandbox@1"

Box = tuple[int, int, int, int]

#: Default tolerances for the returned image. Loosening any of these is a
#: reviewed change: they are what stopped the full-canvas fabric weave.
DEFAULT_TOLERANCES: dict[str, float] = {
    #: Largest per-channel change allowed on a locked pixel.
    "locked_channel_delta": 2,
    #: Share of locked pixels allowed to exceed that delta.
    "locked_pixel_ratio": 0.0005,
    #: Largest RGB distance from a filled pixel to the artwork it borders.
    "colour_distance": 26.0,
    #: Share of filled pixels allowed to exceed that distance. A median would
    #: pass a fill that is right on one edge and wrong on the other.
    "colour_outlier_ratio": 0.10,
    #: Largest filled-to-original ratio of mean absolute Laplacian energy.
    #: Measured on the face sandbox: a correct edge extension sits at 1.15 and
    #: a woven fill at 7.7.
    "texture_energy_ratio": 1.6,
    #: Largest absolute mean absolute Laplacian inside the filled region.
    "texture_energy_absolute": 6.0,
    #: Largest autocorrelation of the filled region's detail at any repeat lag.
    #: Measured on the face sandbox: correct fills sit at 0.20-0.29 and a woven
    #: fill at 0.80.
    "pattern_periodicity": 0.45,
    #: Share of filled pixels allowed to stay partially transparent.
    "soft_alpha_ratio": 0.02,
    #: Filled pixels allowed to fall outside the editable region.
    "spill_pixels": 0,
}


@dataclass(frozen=True, slots=True)
class FileRecord:
    """One file written next to the manifest."""

    name: str
    sha256: str
    role: str

    def to_json(self) -> dict[str, Any]:
        """Return the JSON form."""
        return {"name": self.name, "sha256": self.sha256, "role": self.role}


@dataclass(frozen=True, slots=True)
class Manifest:
    """A parsed sandbox manifest."""

    id: str
    source: dict[str, Any]
    sandbox: dict[str, Any]
    files: dict[str, FileRecord]
    ret: dict[str, Any]
    tolerances: dict[str, float]
    rules: tuple[str, ...]
    raw: dict[str, Any]

    @property
    def canvas(self) -> tuple[int, int]:
        """Return the master document's ``(width, height)``."""
        return tuple(self.source["canvas"])  # type: ignore[return-value]

    @property
    def box(self) -> Box:
        """Return the sandbox crop in canvas coordinates."""
        return tuple(self.sandbox["box"])  # type: ignore[return-value]

    @property
    def size(self) -> tuple[int, int]:
        """Return the sandbox ``(width, height)``."""
        return tuple(self.sandbox["size"])  # type: ignore[return-value]

    @property
    def fill_mode(self) -> str:
        """Return how the sandbox is meant to be filled.

        Sandboxes written before the underlay mode existed carry no field and
        are all edge extensions, so that is the fallback.
        """
        return str(self.sandbox.get("fill_mode", "extend"))

    def path(self, role: str, directory: Path) -> Path:
        """Return the on-disk path of one recorded file."""
        return directory / self.files[role].name

    def tolerance(self, name: str) -> float:
        """Return one tolerance, falling back to the shipped default."""
        return float(self.tolerances.get(name, DEFAULT_TOLERANCES[name]))

    def to_json(self) -> dict[str, Any]:
        """Return the JSON form."""
        return dict(self.raw)


def sha256_bytes(payload: bytes) -> str:
    """Return the hex SHA-256 of a byte string."""
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    """Return the hex SHA-256 of a file, read in chunks so large PSDs fit."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build(
    identifier: str,
    source: dict[str, Any],
    sandbox: dict[str, Any],
    files: dict[str, FileRecord],
    ret: dict[str, Any],
    rules: tuple[str, ...],
    tolerances: dict[str, float] | None = None,
) -> Manifest:
    """Assemble a manifest and its JSON body in one place."""
    merged = dict(DEFAULT_TOLERANCES)
    merged.update(tolerances or {})
    raw = {
        "schema": MANIFEST_SCHEMA,
        "id": identifier,
        "source": source,
        "sandbox": sandbox,
        "files": {role: record.to_json() for role, record in sorted(files.items())},
        "return": ret,
        "rules": list(rules),
        "tolerances": merged,
    }
    return Manifest(identifier, source, sandbox, files, ret, merged, rules, raw)


def dump(manifest: Manifest, path: Path) -> None:
    """Write a manifest as UTF-8 JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(manifest.raw, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    path.write_text(body, encoding="utf-8")


def load(path: Path) -> Manifest:
    """Read a manifest and reject an unknown schema."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    schema = data.get("schema")
    if schema != MANIFEST_SCHEMA:
        raise ValueError(f"unsupported sandbox schema: {schema!r}; expected {MANIFEST_SCHEMA!r}")
    files = {
        role: FileRecord(entry["name"], entry["sha256"], entry["role"])
        for role, entry in data.get("files", {}).items()
    }
    tolerances = dict(DEFAULT_TOLERANCES)
    tolerances.update(data.get("tolerances", {}))
    return Manifest(
        id=data["id"],
        source=data["source"],
        sandbox=data["sandbox"],
        files=files,
        ret=data["return"],
        tolerances=tolerances,
        rules=tuple(data.get("rules", ())),
        raw=data,
    )


def verify_files(manifest: Manifest, directory: Path) -> list[str]:
    """Return a message per recorded file that is missing or has been edited."""
    problems: list[str] = []
    for role, record in sorted(manifest.files.items()):
        path = directory / record.name
        if not path.exists():
            problems.append(f"{role}: {record.name} is missing")
            continue
        actual = sha256_file(path)
        if actual != record.sha256:
            problems.append(f"{role}: {record.name} changed (sha256 {actual[:12]}…)")
    return problems
