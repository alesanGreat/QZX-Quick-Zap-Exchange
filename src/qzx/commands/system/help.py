#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Help command for QZX command discovery."""

from qzx.commands.system._help_response import execute_help
from qzx.core.command_base import CommandBase
from qzx.core.command_loader import CommandLoader

class HelpCommand(CommandBase):
    """
    Muestra la ayuda para un comando específico o la ayuda general del sistema.
    Proporciona información detallada sobre el uso, parámetros y ejemplos de comandos.
    """
    
    name = "help"
    description = "Shows help for a command"
    category = "system"
    parameters = [
        {
            "name": "command",
            "description": "Name of the command to get help for",
            "required": False,
            "default": None
        }
    ]
    examples = [
        {
            "command": "qzx help",
            "description": "Shows general help information"
        },
        {
            "command": "qzx help readFile",
            "description": "Shows detailed help for the readFile command"
        },
        {
            "command": "qzx readFile --help",
            "description": "Shows the same command help with the conventional flag"
        }
    ]

    def __init__(self):
        super().__init__()
        self.command_loader = CommandLoader()
    
    def execute(self, command=None):
        """Show general help or detailed help for one command."""
        return execute_help(self.command_loader, command)
