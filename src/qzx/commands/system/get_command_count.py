#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
WonderCommandsAmount Command - Reports the total number of available commands in QZX
"""

from qzx.core.command_base import CommandBase
from qzx.core.command_loader import CommandLoader

class WonderCommandsAmountCommand(CommandBase):
    """
    Command to check the total number of available commands in QZX
    """
    
    name = "getCommandCount"
    aliases = ["wonderCommandsAmount"]
    description = "Reports the total number of available commands in QZX"
    category = "system"
    
    parameters = []
    
    examples = [
        {
            'command': 'qzx wonderCommandsAmount',
            'description': 'Check how many commands are available in QZX'
        }
    ]
    
    def execute(self):
        """
        Count and report the total number of available commands in QZX
        
        Returns:
            Dictionary with the count of available commands
        """
        try:
            loaded_commands = CommandLoader().discover_commands()
            command_instances = {
                command_class: command_class()
                for command_class in set(loaded_commands.values())
            }
            canonical_names = {
                instance.name.lower() for instance in command_instances.values()
            }
            aliases = {
                alias.lower()
                for instance in command_instances.values()
                for alias in getattr(instance, "aliases", [])
                if alias.lower() not in canonical_names
            }
            alias_count = len(aliases)

            command_count = len(command_instances)
            command_list = sorted(
                instance.name for instance in command_instances.values()
            )
            categories = {}

            for instance in command_instances.values():
                category = instance.category
                categories[category] = categories.get(category, 0) + 1
            
            # Prepare the result
            result = {
                "success": True,
                "command_count": command_count,
                "alias_count": alias_count,
                "total_count": command_count + alias_count,
                "categories": categories,
                "commands": command_list,
                "message": (
                    f"QZX has {command_count} canonical commands and "
                    f"{alias_count} aliases "
                    f"({command_count + alias_count} registered invocations)"
                )
            }
            
            if len(categories) > 0:
                category_report = ", ".join([f"{count} {cat} commands" for cat, count in categories.items()])
                result["message"] += f". Categories: {category_report}"
            
            return result
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Error counting commands: {str(e)}"
            } 
