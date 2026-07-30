"""Allow QZX to run with ``python -m qzx``."""

from . import main


if __name__ == "__main__":
    raise SystemExit(main())
