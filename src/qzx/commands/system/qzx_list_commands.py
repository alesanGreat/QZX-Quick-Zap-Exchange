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
        requested_filter = filter_text

        # Group commands by category
        categories = {}
        
        # Special category for aliases
        alias_category = 'alias'
        categories[alias_category] = []
        
        # Read the packaged metadata index; listing commands must not import
        # every implementation module.
        command_entries = self.command_loader.get_indexed_commands()
        canonical_names = {
            entry["name"].lower() for entry in command_entries
        }
        seen_aliases = set()

        for entry in command_entries:
            maturity = self.command_loader.get_command_maturity(entry["name"])
            categories.setdefault(entry["category"], []).append(
                {
                    "name": entry["name"],
                    "description": entry["description"],
                    "canonical_name": entry["name"],
                    "is_alias": False,
                    "maturity": maturity,
                }
            )
            for alias in entry["aliases"]:
                alias_key = alias.lower()
                if alias_key in canonical_names or alias_key in seen_aliases:
                    continue
                seen_aliases.add(alias_key)
                categories[alias_category].append(
                    {
                        "name": alias,
                        "description": (
                            f"Alias for {entry['name']}: {entry['description']}"
                        ),
                        "canonical_name": entry["name"],
                        "is_alias": True,
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
        
        result = [title]
        canonical_count = sum(
            len(commands)
            for category, commands in categories.items()
            if category != alias_category
        )
        alias_count = len(categories.get(alias_category, []))
        listed_count = canonical_count + alias_count
        category_count = sum(
            1
            for category, commands in categories.items()
            if category != alias_category and commands
        )
        summary = {
            "canonical_commands": canonical_count,
            "aliases": alias_count,
            "listed_entries": listed_count,
            "categories": category_count,
            "filter": requested_filter,
        }
        result.append(
            f"Commands: {canonical_count} canonical, {alias_count} aliases"
        )
        maturity_details = {}
        for category, commands in categories.items():
            if category == alias_category:
                continue
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
        if maturity_summary:
            maturity_text = ", ".join(
                "{} {}".format(details["count"], details["label"])
                for stage, details in ordered_maturity
            )
            result.append(f"Maturity: {maturity_text}")
        
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
            for item in sorted(
                categories[category],
                key=lambda command: command["name"].lower(),
            ):
                result.append(
                    "  {} [{}]: {}".format(
                        item["name"],
                        item["maturity"]["label"],
                        item["description"],
                    )
                )
        
        text_result = "\n".join(result)
        
        # Format the result for consistent output
        return {
            "success": True,
            "message": text_result,
            "summary": summary,
            "maturity_summary": maturity_summary,
            "commands": categories,
        }
