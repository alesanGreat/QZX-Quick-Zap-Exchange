#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
WonderCommandsAmount Command - Reports the total number of available commands in QZX
"""

import inspect
import os
import sys
import importlib
from Core.command_base import CommandBase

class WonderCommandsAmountCommand(CommandBase):
    """
    Command to check the total number of available commands in QZX
    """
    
    name = "wonderCommandsAmount"
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
            # Get all the command classes by finding subclasses of CommandBase
            commands = []
            aliases = {}
            
            # Get current module path
            current_module_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            
            # Look through Command directories
            command_dirs = ['Commands/FileCommands', 'Commands/SystemCommands', 'Commands/DevCommands']
            
            command_count = 0
            alias_count = 0
            command_list = []
            
            # First, check if the standard CommandRegistry is accessible
            try:
                from Core.command_registry import CommandRegistry
                registry = CommandRegistry.instance().get_registry()
                # This has a better chance of working
                command_count = len(registry.commands)
                alias_count = len(registry.aliases)
                command_list = list(registry.commands.keys())
            except:
                # Fallback to manual inspection
                # Find all Command classes by inspecting .py files
                for command_dir in command_dirs:
                    full_dir_path = os.path.join(current_module_path, command_dir)
                    if os.path.exists(full_dir_path):
                        for file in os.listdir(full_dir_path):
                            if file.endswith('.py') and file != '__init__.py':
                                command_name = os.path.splitext(file)[0]
                                command_list.append(command_name)
                                command_count += 1
            
            # Prepare categories
            categories = {}
            
            for cmd in command_list:
                # Determine the category based on the name
                if cmd.startswith("Wonder"):
                    category = "wonder"
                elif cmd in ["AnalyzeComplexity", "CompareFiles", "CreateDocTemplatePython"]:
                    category = "dev"
                elif cmd in ["CopyFile", "DeleteFile", "MoveFile", "ReadFile", "ListFiles", 
                           "FindFiles", "FindText", "TouchFile", "GetHumanLanguageStatsFromFile",
                           "GetProgrammingLanguageStatsFromFile", "FindLargeFiles"]:
                    category = "file"
                else:
                    category = "system"
                
                if category not in categories:
                    categories[category] = 0
                categories[category] += 1
            
            # Prepare the result
            result = {
                "success": True,
                "command_count": command_count,
                "alias_count": alias_count,
                "total_count": command_count + alias_count,
                "categories": categories,
                "commands": command_list,
                "message": f"QZX has {command_count} commands and {alias_count} aliases (total: {command_count + alias_count} commands)"
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