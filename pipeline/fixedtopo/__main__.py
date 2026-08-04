"""Allow ``python -m pipeline.fixedtopo`` to run the command line interface."""

from __future__ import annotations

from pipeline.fixedtopo.cli import main

raise SystemExit(main())
