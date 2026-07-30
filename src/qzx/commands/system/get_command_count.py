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
            command_entries = CommandLoader().get_indexed_commands()
            canonical_names = {
                entry["name"].lower() for entry in command_entries
            }
            aliases = {
                alias.lower()
                for entry in command_entries
                for alias in entry["aliases"]
                if alias.lower() not in canonical_names
            }
            alias_count = len(aliases)

            command_count = len(command_entries)
            command_list = sorted(
                entry["name"] for entry in command_entries
            )
            categories = {}

            for entry in command_entries:
                category = entry["category"]
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
