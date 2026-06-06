#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
QZX Terminal Launcher - Direct launcher for QZX Terminal
This script bypasses the main QZX command processor and launches the terminal directly
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))  # Add current directory to path

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from qzx.commands.system.terminal import QZXTerminalCommand

def main():
    """
    Launch QZX Terminal directly
    """
    # Parse command line arguments (if any)
    args = sys.argv[1:] if len(sys.argv) > 1 else []
    
    # Create and execute the terminal command
    terminal_cmd = QZXTerminalCommand()
    terminal_cmd.execute(*args)

if __name__ == "__main__":
    main() 