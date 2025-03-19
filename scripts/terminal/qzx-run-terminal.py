#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
QZX Terminal Runner - Debug script to test Terminal execution
This script emulates exactly what QZX would do when executing the Terminal command
"""

import sys
import os
from Core.command_loader import CommandLoader

def main():
    """
    Debug the terminal command execution
    """
    print("Loading commands...")
    loader = CommandLoader()
    commands = loader.discover_commands()
    
    # Exactly what QZX would do - get the command and execute it
    print("Looking for Terminal command...")
    command_name = "terminal"  # This is lowercase on purpose
    
    cmd_obj = commands.get(command_name)
    if cmd_obj:
        print(f"Found command: {command_name}")
        # This is what happens in QZX
        cmd_instance = cmd_obj()
        print(f"Executing {cmd_instance.name}...")
        result = cmd_instance.execute()
        print(f"Result: {result}")
    else:
        print(f"Command not found: {command_name}")
        print("Available commands:")
        for name in commands.keys():
            print(f"  - {name}")

if __name__ == "__main__":
    main() 