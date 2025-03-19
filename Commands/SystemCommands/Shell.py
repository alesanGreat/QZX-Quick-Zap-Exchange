#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Shell Command - Redirects to Terminal command
"""

from Core.command_base import CommandBase
from Commands.SystemCommands.Terminal import QZXTerminalCommand

class QZXShellCommand(CommandBase):
    """
    Shell command - Alias for the Terminal command
    This is just a compatibility wrapper that redirects to the Terminal command
    """
    
    name = "Shell"
    aliases = ["Terminal", "Console", "REPL"]  # Ensure bidirectional aliasing
    description = "Launches an interactive shell for QZX commands (alias for Terminal)"
    category = "system"
    
    # Same parameters as Terminal
    parameters = QZXTerminalCommand.parameters
    
    # Same examples as Terminal
    examples = [
        {
            'command': 'qzx Shell',
            'description': 'Launch the QZX interactive shell with default settings'
        },
        {
            'command': 'qzx Shell "MyQZX> "',
            'description': 'Launch the QZX shell with a custom prompt'
        }
    ]
    
    def execute(self, *args, **kwargs):
        """
        Execute the Shell command by redirecting to Terminal
        
        Args:
            *args: Arguments to pass to Terminal
            **kwargs: Keyword arguments to pass to Terminal
            
        Returns:
            Result from the Terminal command
        """
        # Create Terminal command instance and execute it
        terminal_cmd = QZXTerminalCommand()
        return terminal_cmd.execute(*args, **kwargs) 