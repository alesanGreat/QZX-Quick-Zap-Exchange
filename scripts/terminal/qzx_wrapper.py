#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
QZX Wrapper - Case-insensitive wrapper for QZX
This script ensures all QZX commands are case-insensitive by converting 
command names to lowercase before passing them to the main QZX system
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from qzx.cli import main as qzx_main

def main():
    """
    Main entry point for the QZX wrapper
    """
    args = sys.argv[1:]
    if args:
        args[0] = args[0].lower()
    sys.argv = [sys.argv[0], *args]
    qzx_main()

if __name__ == "__main__":
    main()
