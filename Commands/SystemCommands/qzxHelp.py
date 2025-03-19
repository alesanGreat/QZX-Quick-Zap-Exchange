#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
qzxHelp - Muestra la ayuda para un comando específico o la ayuda general del sistema.
"""

from Core.command_base import CommandBase
from Core.command_loader import CommandLoader

class qzxHelp(CommandBase):
    """
    Muestra la ayuda para un comando específico o la ayuda general del sistema.
    Proporciona información detallada sobre el uso, parámetros y ejemplos de comandos.
    """
    
    def __init__(self):
        super().__init__()
        self.name = "qzxHelp"
        self.description = "Show help for a command"
        self.category = "system"
        self.aliases = ["help"]
        self.parameters = [
            {
                "name": "command",
                "description": "Name of the command to get help for",
                "required": False,
                "default": None
            }
        ]
        self.examples = [
            {
                "command": "qzxHelp",
                "description": "Shows general help information"
            },
            {
                "command": "help readFile",
                "description": "Shows detailed help for the readFile command"
            }
        ]
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
            
Usage: qzx <command> [arguments]

Commands:
- To see a list of all available commands: qzx list
- To get help on a specific command: qzx help <command>
- To see system information: qzx WonderMyEnvironment
- To display this welcome message: qzx Welcome (or just qzx)
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