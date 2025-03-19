#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
QZX: Quick Zap Exchange - Universal Command Interface for AI Agents
Modular Version
"""

import os
import sys
import importlib
import argparse
from Core.qzx_core import QZXCore

def main():
    """
    Entry point for the QZX command line interface
    """
    parser = argparse.ArgumentParser(description="QZX: Universal Command Interface")
    parser.add_argument('command', help='Command to execute')
    parser.add_argument('args', nargs='*', help='Command arguments')
    
    if len(sys.argv) < 2:
        parser.print_help()
        sys.exit(1)
    
    args = parser.parse_args()
    
    # Initialize the QZX core which will load and manage all commands
    qzx = QZXCore()
    
    # Execute the requested command
    result = qzx.execute(args.command, args.args)
    print(result)

if __name__ == "__main__":
    main() 