#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""QZX - Quick Zap Exchange."""

__version__ = "0.2.2"


def main():
    """Run the QZX command-line interface."""
    from .cli import main as cli_main

    return cli_main()


__all__ = ["__version__", "main"]
