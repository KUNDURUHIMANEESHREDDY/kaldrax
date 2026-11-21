"""Frozen executable entrypoint for the KALDRAX command-line application."""

from kaldrax.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
