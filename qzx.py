#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
QZX: Quick Zap Exchange - Universal Command Interface for AI Agents
"""

import os
import sys
import subprocess
import platform
import argparse
from Core.command_loader import CommandLoader

# Try to import psutil, or install it if missing
try:
    import psutil
except ImportError:
    print("Warning: psutil module not found. Some system commands may not work.")
    print("Attempting to install psutil...")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "psutil"],
            capture_output=True,
            text=True,
            check=False
        )
        try:
            import psutil
            print("Successfully installed psutil.")
        except ImportError:
            print("Failed to automatically install psutil. Install it manually with: pip install psutil")
            psutil = None
    except Exception:
        print("Failed to automatically install psutil. Install it manually with: pip install psutil")
        psutil = None

# Try to import pyreadline3 on Windows for better command line experience
if platform.system().lower() == 'windows':
    try:
        import pyreadline3
    except ImportError:
        print("Warning: pyreadline3 module not found. Command history and editing will be limited.")
        print("Attempting to install pyreadline3...")
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "pyreadline3"],
                capture_output=True,
                text=True,
                check=False
            )
            try:
                import pyreadline3
                print("Successfully installed pyreadline3.")
            except ImportError:
                print("Failed to automatically install pyreadline3. Install it manually with: pip install pyreadline3")
        except Exception:
            print("Failed to automatically install pyreadline3. Install it manually with: pip install pyreadline3")

class QZX:
    def __init__(self):
        self.os_type = platform.system().lower()
        self.version = "0.02"
        
        # Initialize command loader
        self.command_loader = CommandLoader()
        
        # Load modular commands
        self.modular_commands = self.command_loader.discover_commands()
        
        # Legacy built-in commands (will be migrated to modular system)
        self.built_in_commands = {
            # All commands have been migrated to their own files!
        }
        
        # Combine all commands (modular commands take precedence)
        self.commands = {**self.built_in_commands, **self.modular_commands}
    
    def execute(self, command, args=None):
        """Execute a command with arguments"""
        if not args:
            args = []
        
        # Special handling for built-in commands
        if command == "help":
            if args:
                return self.show_help(args[0])
            else:
                return self.show_help()
        
        # Special handling for list command with filter
        if command == "list":
            if args and len(args) > 0:
                return self.list_commands(args[0])
            else:
                return self.list_commands()
        
        # Execute a built-in command
        if command in self.built_in_commands:
            return self.built_in_commands[command](*args)
        
        # Execute a modular command
        cmd_obj = self.command_loader.get_command(command)
        if cmd_obj:
            # Validate parameters before execution
            is_valid, error_message = cmd_obj.validate_parameters(args)
            if not is_valid:
                return error_message
            
            # If parameters are valid, execute the command
            result = cmd_obj.execute(*args)
            
            # Format the result to ensure consistency
            return cmd_obj.format_result(result)
        
        # List all commands by category
        return self.list_commands()
    
    def show_help(self, command=None):
        """Show help for a command"""
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
        
        # Find the command
        if command in self.built_in_commands:
            help_text = f"Command: {command}\n\n"
            if self.built_in_commands[command].__doc__:
                help_text += self.built_in_commands[command].__doc__
            else:
                help_text += "No help available for this command."
                
            return {
                "success": True,
                "command": command,
                "message": help_text
            }
        
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
    
    def list_commands(self, filter_text=None):
        """
        List all available commands
        
        Args:
            filter_text (str, optional): Text to filter commands by name or description
        """
        # Group commands by category
        categories = {}
        
        # Special category for aliases
        alias_category = 'alias'
        categories[alias_category] = []
        
        # Track original commands to identify aliases
        original_commands = {}
        command_instances = {}
        
        # First pass: identify and store original commands
        for name, cmd_class in self.modular_commands.items():
            # Instantiate the command once
            if cmd_class not in command_instances:
                command_instances[cmd_class] = cmd_class()
                
            cmd_instance = command_instances[cmd_class]
            original_name = cmd_instance.name
            
            # Store mapping of original command name to its command class
            if original_name == name:
                original_commands[original_name] = cmd_class
        
        # Second pass: categorize commands
        for name, cmd_class in self.modular_commands.items():
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
        
        # Process legacy built-in commands (if any)
        for name, cmd in self.built_in_commands.items():
            # Default category for built-in commands
            category = 'built-in'
            if category not in categories:
                categories[category] = []
            
            # Get description from docstring
            doc = cmd.__doc__ or "No description"
            description = doc.strip().split('\n')[0]
            categories[category].append((name, description))
        
        # Add special commands
        categories['system'] = categories.get('system', [])
        categories['system'].append(('help', 'Show help for a command'))
        categories['system'].append(('list', 'List all available commands'))
        
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


def main():
    # Modificación para manejar correctamente opciones como -r, --recursive, etc.
    if len(sys.argv) < 2:
        # En lugar de mostrar mensaje de uso, ejecutamos Welcome por defecto
        qzx = QZX()
        result = qzx.execute("Welcome")
        
        # Mostrar el resultado
        if isinstance(result, dict) and "message" in result:
            print(result["message"])
        else:
            print(result)
        
        sys.exit(0)
    
    command = sys.argv[1]
    
    # Check if json output is requested
    json_output = False
    filtered_args = []
    
    for arg in sys.argv[2:]:
        if arg == '--json' or arg == '-json':
            json_output = True
        else:
            filtered_args.append(arg)
    
    # Pasamos los argumentos filtrados (sin los flags de formato) al comando
    args = filtered_args
    
    qzx = QZX()
    result = qzx.execute(command, args)
    
    # Format and print the result according to the requested output format
    if json_output:
        # If result is already a dictionary, use it directly
        # Otherwise wrap it in a simple dictionary
        import json
        if isinstance(result, dict):
            print(json.dumps(result, indent=2))
        else:
            print(json.dumps({"result": result}, indent=2))
    else:
        # For natural language output, check if it's a dictionary with a message field
        if isinstance(result, dict) and "message" in result:
            print(result["message"])
        else:
            print(result)


if __name__ == "__main__":
    main() 