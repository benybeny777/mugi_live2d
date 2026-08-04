"""Allow ``python -m pipeline.keyform``."""

from __future__ import annotations

from pipeline.keyform.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
