"""Allow ``python -m pipeline.sandbox``."""

from pipeline.sandbox.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
