#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
qzxHelp - Muestra la ayuda para un comando específico o la ayuda general del sistema.
"""

from qzx.core.command_base import CommandBase
from qzx.core.command_loader import CommandLoader

class qzxHelp(CommandBase):
    """
    Muestra la ayuda para un comando específico o la ayuda general del sistema.
    Proporciona información detallada sobre el uso, parámetros y ejemplos de comandos.
    """
    
    name = "qzxHelp"
    description = "Shows help for a command"
    category = "system"
    aliases = ["help"]
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
            "command": "qzx qzxHelp",
            "description": "Shows general help information"
        },
        {
            "command": "qzx help readFile",
            "description": "Shows detailed help for the readFile command"
        }
    ]

    def __init__(self):
        super().__init__()
        self.command_loader = CommandLoader()
    
    def execute(self, command=None):
        """
        Muestra la ayuda para un comando específico o la ayuda general del sistema.
        
        Args:
            command (str, optional): Nombre del comando para el que se quiere obtener ayuda
            
        Returns:
            dict: Diccionario con la información de ayuda solicitada
        """
        if not command:
            # General help - list all commands
            help_text = """QZX Help:

Usage: qzx <command> [arguments] [--json]

Output:
- Without --json: a clear terminal presentation with the summary and useful data.
- With --json: one complete structured object on stdout.
- Every public result contains boolean success and descriptive message fields.

Discovery:
- List the commands in this installation: qzx list --json
- Inspect one command: qzx help <command> --json
- Identify this installation: qzx version --json

Naming:
- Command lookup is case-insensitive.
- Documentation uses each command's canonical lowerCamelCase spelling.
- Accepted aliases appear in command-specific help and the public catalog.
"""
            
            return {
                "success": True,
                "message": help_text
            }
        
        # Find the command using the command loader
        cmd_obj = self.command_loader.get_command(command)
        if cmd_obj:
            help_text = cmd_obj.get_help()
            
            return {
                "success": True,
                "command": command,
                "message": help_text,
                "details": {
                    "name": cmd_obj.name,
                    "description": cmd_obj.description,
                    "category": cmd_obj.category,
                    "parameters": cmd_obj.parameters,
                    "examples": cmd_obj.examples
                }
            }
        
        return {
            "success": False,
            "error": f"Command not found: {command}",
            "message": f"Command not found: {command}"
        }
