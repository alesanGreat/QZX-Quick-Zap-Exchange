#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
QZX Terminal - Direct launcher for QZX Terminal
Simplified script that launches the QZX Terminal directly
"""

import sys
import os
from Commands.SystemCommands.Terminal import QZXTerminalCommand

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