#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Test script for ListFiles command arguments
"""

import sys
from Commands.FileCommands.ListFiles import ListFilesCommand

def main():
    # Argument analysis
    print("Arguments received:", sys.argv[1:])
    
    # Create command instance
    cmd = ListFilesCommand()
    
    # Parse the arguments
    args = sys.argv[1:] if len(sys.argv) > 1 else []
    
    # Print parameters
    if len(args) >= 1:
        dir_path = args[0]
    else:
        dir_path = "."
    print(f"Directory path: {dir_path}")
    
    if len(args) >= 2:
        pattern = args[1]
    else:
        pattern = "*"
    print(f"Pattern: {pattern}")
    
    recursive = None
    if len(args) >= 3:
        recursive = args[2]
    print(f"Recursive: {recursive}")
    
    # Call the execute method directly
    print("\nExecuting command...")
    result = cmd.execute(dir_path, pattern, recursive)
    
    print("\nCommand result:")
    print(result)

if __name__ == "__main__":
    main() 