#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""List the QZX commands available in this installation."""

from qzx.commands.system._command_catalog import build_command_catalog_result
from qzx.core.command_base import CommandBase
from qzx.core.command_loader import CommandLoader

class ListCommandsCommand(CommandBase):
    """
    Lista todos los comandos disponibles en QZX, organizados por categoría.
    Permite filtrar comandos por nombre o descripción.
    """
    
    name = "listCommands"
    description = "Lists all available commands organized by category"
    category = "system"
    parameters = [
        {
            "name": "filter_text",
            "description": "Optional text to filter commands by name or description",
            "required": False,
            "default": None
        }
    ]
    examples = [
        {
            "command": "qzx listCommands",
            "description": "Lists all available commands organized by category"
        },
        {
            "command": "qzx listCommands file",
            "description": "Lists all commands containing 'file' in their name or description"
        }
    ]

    def __init__(self):
        super().__init__()
        self.command_loader = CommandLoader()
    
    def execute(self, filter_text=None):
        """List the available commands, optionally filtered by text."""
        return build_command_catalog_result(self.command_loader, filter_text)
