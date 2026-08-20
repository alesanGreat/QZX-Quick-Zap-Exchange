#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""List the QZX commands available in this installation."""

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
        """
        Lists all available commands organized by category.
        
        Args:
            filter_text (str, optional): Text to filter commands by name or description
            
        Returns:
            dict: Dictionary containing list of commands organized by category
        """
        requested_filter = filter_text

        categories = {}

        # Read the packaged metadata index; listing commands must not import
        # every implementation module.
        command_entries = self.command_loader.get_indexed_commands()

        for entry in command_entries:
            maturity = self.command_loader.get_command_maturity(entry["name"])
            categories.setdefault(entry["category"], []).append(
                {
                    "name": entry["name"],
                    "description": entry["description"],
                    "maturity": maturity,
                }
            )

        for commands in categories.values():
            commands.sort(key=lambda command: command["name"].lower())
        
        # Apply filter if provided
        if filter_text:
            normalized_filter = filter_text.lower()
            filtered_categories = {}
            
            for category, commands in categories.items():
                filtered_commands = [
                    item for item in commands
                    if (
                        normalized_filter in item["name"].lower()
                        or normalized_filter in item["description"].lower()
                        or normalized_filter in item["maturity"]["stage"]
                        or normalized_filter in item["maturity"]["label"].lower()
                    )
                ]
                
                if filtered_commands:
                    filtered_categories[category] = filtered_commands
            
            categories = filtered_categories
        
        # Prepare output
        if filter_text:
            title = f"Available Commands (filtered by '{requested_filter}')"
        else:
            title = "Available Commands"
        
        command_count = sum(len(commands) for commands in categories.values())
        category_count = sum(1 for commands in categories.values() if commands)
        summary = {
            "commands": command_count,
            "categories": category_count,
            "filter": requested_filter,
        }
        maturity_details = {}
        for commands in categories.values():
            for item in commands:
                stage = item["maturity"]["stage"]
                details = maturity_details.setdefault(
                    stage,
                    {
                        "count": 0,
                        "label": item["maturity"]["label"],
                        "sequence": item["maturity"]["sequence"],
                    },
                )
                details["count"] += 1
        ordered_maturity = sorted(
            maturity_details.items(),
            key=lambda entry: entry[1]["sequence"],
        )
        maturity_summary = {
            stage: details["count"]
            for stage, details in ordered_maturity
        }

        # Format the result for consistent output
        return {
            "success": True,
            "message": f"{title}\nCommands: {command_count}",
            "summary": summary,
            "maturity_summary": maturity_summary,
            "commands": categories,
        }
