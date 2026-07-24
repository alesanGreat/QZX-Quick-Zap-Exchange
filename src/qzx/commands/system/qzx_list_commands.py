#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
qzxListCommands - Lista todos los comandos disponibles organizados por categoría.
"""

from qzx.core.command_base import CommandBase
from qzx.core.command_loader import CommandLoader

class qzxListCommands(CommandBase):
    """
    Lista todos los comandos disponibles en QZX, organizados por categoría.
    Permite filtrar comandos por nombre o descripción.
    """
    
    name = "qzxListCommands"
    description = "Lists all available commands organized by category"
    category = "system"
    aliases = ["list", "ListCommands"]
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
            "command": "qzx qzxListCommands",
            "description": "Lists all available commands organized by category"
        },
        {
            "command": "qzx list file",
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
        # Group commands by category
        categories = {}
        
        # Special category for aliases
        alias_category = 'alias'
        categories[alias_category] = []
        
        # Get all commands from command loader
        all_commands = self.command_loader.get_all_commands()
        command_instances = [
            command_class() for command_class in set(all_commands.values())
        ]
        canonical_names = {
            instance.name.lower() for instance in command_instances
        }
        seen_aliases = set()

        for instance in command_instances:
            categories.setdefault(instance.category, []).append(
                (instance.name, instance.description)
            )
            for alias in getattr(instance, "aliases", []):
                alias_key = alias.lower()
                if alias_key in canonical_names or alias_key in seen_aliases:
                    continue
                seen_aliases.add(alias_key)
                categories[alias_category].append(
                    (
                        alias,
                        f"Alias for {instance.name}: {instance.description}",
                    )
                )
        
        # Apply filter if provided
        if filter_text:
            filter_text = filter_text.lower()
            filtered_categories = {}
            
            for category, commands in categories.items():
                filtered_commands = [
                    (name, desc) for name, desc in commands 
                    if filter_text in name.lower() or filter_text in desc.lower()
                ]
                
                if filtered_commands:
                    filtered_categories[category] = filtered_commands
            
            categories = filtered_categories
        
        # Prepare output
        if filter_text:
            title = f"Available Commands (filtered by '{filter_text}')"
        else:
            title = "Available Commands"
        
        result = [title]
        
        # Sort categories (put 'alias' last)
        sorted_categories = sorted([c for c in categories.keys() if c != alias_category])
        if alias_category in categories and categories[alias_category]:
            sorted_categories.append(alias_category)
        
        # Generate output for each category
        for category in sorted_categories:
            # Skip empty categories
            if not categories[category]:
                continue
                
            result.append(f"\n[{category.upper()}]")
            # Sort commands within category
            for name, description in sorted(categories[category]):
                result.append(f"  {name}: {description}")
        
        text_result = "\n".join(result)
        
        # Format the result for consistent output
        return {
            "success": True,
            "message": text_result,
            "commands": {
                category: [{"name": name, "description": desc} for name, desc in commands]
                for category, commands in categories.items()
            }
        }
