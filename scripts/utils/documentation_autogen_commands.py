#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Documentation Auto Generator for Commands - Generates markdown documentation from command classes
"""

import os
import importlib
import inspect
import pkgutil
import sys
from pathlib import Path
from datetime import datetime

# Add root directory to path so we can import modules from it
root_dir = Path(__file__).resolve().parents[2]
sys.path.append(str(root_dir))

try:
    from Core.command_base import CommandBase
except ImportError:
    print("Error: Cannot import CommandBase. Make sure you're running this from the project root.")
    sys.exit(1)

# Output file path
OUTPUT_FILE = os.path.join(root_dir, "Documentation", "Documentation-Commands-AutoGen.md")

def get_commands_directories():
    """Returns a list of directories that contain commands"""
    commands_dir = os.path.join(root_dir, "Commands")
    if not os.path.exists(commands_dir):
        print(f"Error: Commands directory not found at {commands_dir}")
        return []
        
    result = []
    for item in os.listdir(commands_dir):
        item_path = os.path.join(commands_dir, item)
        if os.path.isdir(item_path) and not item.startswith('__'):
            result.append(item_path)
    
    return result

def discover_command_modules():
    """Discovers all command modules in the Commands directory and subdirectories"""
    command_modules = []
    
    for commands_dir in get_commands_directories():
        # Get the package name from the directory path (e.g., "Commands.SystemCommands")
        package_name = os.path.relpath(commands_dir, root_dir).replace(os.path.sep, '.')
        
        print(f"Exploring package: {package_name} at {commands_dir}")
        
        try:
            # Import the package
            package = importlib.import_module(package_name)
            
            # Find all modules in the package
            for _, module_name, is_pkg in pkgutil.iter_modules([commands_dir]):
                if not is_pkg and not module_name.startswith('__'):
                    try:
                        # Import the module
                        full_module_name = f"{package_name}.{module_name}"
                        print(f"  Importing module: {full_module_name}")
                        module = importlib.import_module(full_module_name)
                        command_modules.append(module)
                    except ImportError as e:
                        print(f"  Warning: Could not import {package_name}.{module_name}: {str(e)}")
                    except Exception as e:
                        print(f"  Error importing {package_name}.{module_name}: {str(e)}")
        except ImportError as e:
            print(f"Warning: Could not import package {package_name}: {str(e)}")
        except Exception as e:
            print(f"Error exploring package {package_name}: {str(e)}")
    
    return command_modules

def find_command_classes(modules):
    """Finds all classes that inherit from CommandBase in the given modules"""
    command_classes = []
    
    for module in modules:
        try:
            print(f"Finding command classes in {module.__name__}")
            for name, obj in inspect.getmembers(module):
                if (inspect.isclass(obj) and 
                    issubclass(obj, CommandBase) and 
                    obj is not CommandBase):
                    print(f"  Found command class: {obj.__name__}")
                    command_classes.append(obj)
        except Exception as e:
            print(f"Error inspecting module {module.__name__}: {str(e)}")
    
    return command_classes

def sort_command_classes(command_classes):
    """Sorts command classes by category and name"""
    return sorted(command_classes, key=lambda cmd: (cmd.category, cmd.name))

def group_by_category(command_classes):
    """Groups command classes by their category"""
    categories = {}
    
    for cmd_class in command_classes:
        category = cmd_class.category
        if category not in categories:
            categories[category] = []
        categories[category].append(cmd_class)
    
    return categories

def format_parameters(parameters):
    """Formats command parameters for markdown"""
    if not parameters:
        return "None"
    
    result = []
    for param in parameters:
        name = param.get('name', 'unnamed')
        desc = param.get('description', 'No description')
        required = param.get('required', False)
        default = param.get('default', None)
        
        req_text = "Required" if required else "Optional"
        default_text = f" (default: `{default}`)" if default is not None else ""
        
        result.append(f"- `{name}`: {desc} - {req_text}{default_text}")
    
    return "\n".join(result)

def format_examples(examples):
    """Formats command examples for markdown"""
    if not examples:
        return "None"
    
    result = []
    for example in examples:
        cmd = example.get('command', '')
        desc = example.get('description', 'No description')
        
        result.append(f"- `{cmd}`\n  {desc}")
    
    return "\n".join(result)

def generate_command_doc(cmd_class):
    """Generates markdown documentation for a command class"""
    doc = []
    
    # Class docstring
    class_doc = inspect.getdoc(cmd_class)
    
    # Command header
    doc.append(f"### {cmd_class.name}")
    if class_doc:
        doc.append(f"\n{class_doc}\n")
    
    # Basic information
    doc.append(f"**Category:** {cmd_class.category}")
    if cmd_class.aliases:
        aliases_str = ", ".join([f"`{alias}`" for alias in cmd_class.aliases])
        doc.append(f"**Aliases:** {aliases_str}")
    doc.append(f"**Description:** {cmd_class.description}")
    
    # Parameters
    doc.append("\n**Parameters:**")
    doc.append(format_parameters(cmd_class.parameters))
    
    # Examples
    if cmd_class.examples:
        doc.append("\n**Examples:**")
        doc.append(format_examples(cmd_class.examples))
    
    # Execute method documentation
    if hasattr(cmd_class, 'execute'):
        execute_doc = inspect.getdoc(cmd_class.execute)
        if execute_doc:
            doc.append("\n**Details:**")
            doc.append(execute_doc)
    
    return "\n".join(doc)

def generate_toc(categories):
    """Generates a table of contents for the documentation"""
    toc = ["## Table of Contents\n"]
    
    for category in sorted(categories.keys()):
        category_display = category.capitalize()
        toc.append(f"- [{category_display} Commands](#{category}-commands)")
        
        for cmd_class in sorted(categories[category], key=lambda c: c.name):
            toc.append(f"  - [{cmd_class.name}](#{cmd_class.name.lower()})")
    
    return "\n".join(toc)

def generate_markdown(categories):
    """Generates the full markdown documentation"""
    lines = []
    
    # Header
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines.append("# QZX Commands Documentation")
    lines.append("\n> This file has been automatically generated by documentation_autogen_commands.py. Do not modify by hand.")
    lines.append(f"> Generated on: {timestamp}\n")
    
    # Table of Contents
    lines.append(generate_toc(categories))
    
    # Command documentation by category
    for category in sorted(categories.keys()):
        category_display = category.capitalize()
        lines.append(f"\n## {category_display} Commands\n")
        
        for cmd_class in sorted(categories[category], key=lambda c: c.name):
            lines.append(generate_command_doc(cmd_class))
            lines.append("\n---\n")
    
    return "\n".join(lines)

def main():
    print("Generating commands documentation...")
    print(f"Working directory: {os.getcwd()}")
    print(f"Script location: {os.path.dirname(os.path.abspath(__file__))}")
    print(f"Root directory: {root_dir}")
    print(f"Output file path: {OUTPUT_FILE}")
    
    try:
        # Discover all command modules
        print("Discovering command modules...")
        command_dirs = get_commands_directories()
        print(f"Command directories: {command_dirs}")
        
        modules = discover_command_modules()
        print(f"Found {len(modules)} command modules")
        
        # Find all command classes
        print("Finding command classes...")
        command_classes = find_command_classes(modules)
        print(f"Found {len(command_classes)} command classes")
        
        if not command_classes:
            print("No command classes found. Check import paths and class inheritance.")
            return
        
        # Group by category
        categories = group_by_category(command_classes)
        print(f"Found {len(categories)} command categories: {', '.join(categories.keys())}")
        
        # Generate markdown
        print("Generating markdown...")
        markdown = generate_markdown(categories)
        
        # Write to file
        print(f"Writing to {OUTPUT_FILE}...")
        os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
        
        # Test if we can write to the output directory
        test_file = os.path.join(os.path.dirname(OUTPUT_FILE), "test_write_permission.txt")
        try:
            with open(test_file, 'w') as f:
                f.write("Test")
            os.remove(test_file)
            print("Write permission test passed")
        except Exception as e:
            print(f"Error testing write permission: {str(e)}")
            
        # Write the actual documentation file
        try:
            with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
                f.write(markdown)
            print(f"Documentation successfully generated at {OUTPUT_FILE}")
        except Exception as e:
            print(f"Error writing documentation file: {str(e)}")
            
            # Try writing to a different location
            alternative_path = os.path.join(os.getcwd(), "Documentation-Commands-AutoGen.md")
            print(f"Trying alternative path: {alternative_path}")
            with open(alternative_path, 'w', encoding='utf-8') as f:
                f.write(markdown)
            print(f"Documentation written to alternative path: {alternative_path}")
            
    except Exception as e:
        print(f"Error generating documentation: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
