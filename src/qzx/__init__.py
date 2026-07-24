#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""QZX - Quick Zap Exchange."""

import json
from importlib import resources


def _development_version():
    manifest = resources.files("qzx.resources").joinpath("product-manifest.json")
    with manifest.open("r", encoding="utf-8") as handle:
        return json.load(handle)["channels"]["development"]["version"]


__version__ = _development_version()


def main():
    """Run the QZX command-line interface."""
    from .cli import main as cli_main

    return cli_main()


__all__ = ["__version__", "main"]
