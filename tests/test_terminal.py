#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Quick test script for QZX Terminal functionality
"""

from Commands.SystemCommands.Terminal import QZXTerminalCommand

def main():
    """
    Direct test of the Terminal command without going through the main QZX interface
    This helps isolate any issues with the command itself vs. the command invocation
    """
    print("Starting QZX Terminal directly...")
    terminal = QZXTerminalCommand()
    terminal.execute()

if __name__ == "__main__":
    main() 