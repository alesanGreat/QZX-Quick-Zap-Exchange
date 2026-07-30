#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""QZX - Quick Zap Exchange."""

from ._build_info import VERSION as __version__


def main():
    """Run the QZX command-line interface."""
    import sys

    arguments = sys.argv[1:]
    if not arguments:
        from .fast_startup import main as fast_main

        return fast_main()

    from .cli import main as cli_main

    return cli_main()


__all__ = ["__version__", "main"]
