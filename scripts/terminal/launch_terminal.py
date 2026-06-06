#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
QZX Terminal - Direct launcher for QZX Terminal
Simplified script that launches the QZX Terminal directly
"""

import sys
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from qzx.commands.system.terminal import QZXTerminalCommand

def main():
    """
    Launch the QZX Terminal
    """
    print("Starting QZX Terminal...")
    terminal = QZXTerminalCommand()
    result = terminal.execute()
    
    # If there was an error, print it
    if isinstance(result, dict) and not result.get("success", False):
        print(f"Error: {result.get('error', 'Unknown error')}")
        sys.exit(1)

if __name__ == "__main__":
    main() 