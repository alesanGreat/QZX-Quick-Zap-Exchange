#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
qzxListCommands - Lista todos los comandos disponibles organizados por categoría.
"""

from Core.command_base import CommandBase
from Core.command_loader import CommandLoader

class qzxListCommands(CommandBase):
    """
    Lista todos los comandos disponibles en QZX, organizados por categoría.
    Permite filtrar comandos por nombre o descripción.
    """
    
    def __init__(self):
        super().__init__()
        self.name = "qzxListCommands"
        self.description = "Lists all available commands organized by category"
        self.category = "system"
        self.aliases = ["list", "ListCommands"]
        self.parameters = [
            {
                "name": "filter_text",
                "description": "Optional text to filter commands by name or description",
                "required": False,
                "default": None
            }
        ]
        self.examples = [
            {
                "command": "qzxListCommands",
                "description": "Lists all available commands organized by category"
            },
            {
                "command": "list file",
                "description": "Lists all commands containing 'file' in their name or description"
            }
        ]
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
        
        # Track original commands to identify aliases
        original_commands = {}
        command_instances = {}
        
        # Get all commands from command loader
        all_commands = self.command_loader.get_all_commands()
        
        # First pass: identify and store original commands
        for name, cmd_class in all_commands.items():
            # Instantiate the command once
            if cmd_class not in command_instances:
                command_instances[cmd_class] = cmd_class()
                
            cmd_instance = command_instances[cmd_class]
            original_name = cmd_instance.name
            
            # Store mapping of original command name to its command class
            if original_name == name:
                original_commands[original_name] = cmd_class
        
        # Second pass: categorize commands
        for name, cmd_class in all_commands.items():
            cmd_instance = command_instances[cmd_class]
            original_name = cmd_instance.name
            category = cmd_instance.category
            description = cmd_instance.description
            
            # Initialize the category if it doesn't exist
            if category not in categories:
                categories[category] = []
            
            # If this is the original command name, add to its proper category
            if name == original_name:
                categories[category].append((name, description))
            # Otherwise, it's an alias, add to the alias category with reference to original
            elif name.lower() == original_name.lower():
                # Skip duplicate lowercase aliases
                continue
            else:
                # It's an actual alias, add it to alias category with reference to its original command
                categories[alias_category].append((name, f"Alias for {original_name}: {description}"))
        
        # Add special commands
        categories['system'] = categories.get('system', [])
        categories['system'].append(('qzxHelp', 'Show help for a command'))
        
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