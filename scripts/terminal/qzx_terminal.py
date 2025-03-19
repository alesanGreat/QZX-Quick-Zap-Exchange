#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
QZX Terminal Launcher - Direct launcher for QZX Terminal
This script bypasses the main QZX command processor and launches the terminal directly
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))  # Add current directory to path

from Commands.SystemCommands.Terminal import QZXTerminalCommand

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