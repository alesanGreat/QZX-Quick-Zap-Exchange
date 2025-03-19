#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
QZX Wrapper - Case-insensitive wrapper for QZX
This script ensures all QZX commands are case-insensitive by converting 
command names to lowercase before passing them to the main QZX system
"""

import sys
import os
import importlib.util
import subprocess

def main():
    """
    Main entry point for the QZX wrapper
    """
    # Get the directory of this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Path to the original qzx.py script
    qzx_path = os.path.join(script_dir, "qzx.py")
    
    # Verify qzx.py exists
    if not os.path.exists(qzx_path):
        print(f"Error: Could not find qzx.py at {qzx_path}")
        sys.exit(1)
    
    # Get command line arguments, excluding the script name
    args = sys.argv[1:]
    
    if not args:
        # No arguments, show help
        subprocess.run([sys.executable, qzx_path])
        return
    
    # Get the command (first argument) and convert to lowercase
    command = args[0].lower()
    
    # Check if it's the term/terminal/shell command
    if command in ['term', 'terminal', 'shell', 'console', 'repl']:
        # Call our direct terminal launcher instead
        term_path = os.path.join(script_dir, "qzx_terminal.py")
        if os.path.exists(term_path):
            # Pass any additional arguments
            subprocess.run([sys.executable, term_path] + args[1:])
        else:
            print("Error: Could not find terminal launcher script")
            sys.exit(1)
    else:
        # For all other commands, call the original qzx.py with lowercase command
        subprocess.run([sys.executable, qzx_path, command] + args[1:])

if __name__ == "__main__":
    main() 