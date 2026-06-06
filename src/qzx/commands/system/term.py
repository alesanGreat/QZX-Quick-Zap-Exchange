#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Term Command - Special alias for Terminal with case-insensitive variants
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from qzx.core.command_base import CommandBase
from qzx.commands.system.terminal import QZXTerminalCommand

class QZXTermCommand(CommandBase):
    """
    Term command - Special alias for Terminal with various case variants
    This command ensures the terminal can be started regardless of capitalization
    """
    
    name = "term"
    # Include many case variations to ensure it works
    aliases = [
        "terminal", "Terminal", "TERMINAL", 
        "shell", "Shell", "SHELL",
        "console", "Console", "CONSOLE",
        "repl", "REPL", "Repl",
        "term", "TERM"
    ]
    description = "Launches an interactive QZX terminal (case-insensitive alias)"
    category = "system"
    
    # Same parameters as Terminal
    parameters = QZXTerminalCommand.parameters
    
    # Simple examples
    examples = [
        {
            'command': 'qzx term',
            'description': 'Launch the QZX interactive terminal (case-insensitive)'
        },
        {
            'command': 'qzx terminal',
            'description': 'Also launches the QZX terminal (lowercase variant)'
        }
    ]
    
    def execute(self, *args, **kwargs):
        """
        Execute the Term command by redirecting to Terminal
        
        Args:
            *args: Arguments to pass to Terminal
            **kwargs: Keyword arguments to pass to Terminal
            
        Returns:
            Result from the Terminal command
        """
        # Create Terminal command instance and execute it
        terminal_cmd = QZXTerminalCommand()
        # Pass all arguments to the terminal command
        return terminal_cmd.execute(*args, **kwargs) 