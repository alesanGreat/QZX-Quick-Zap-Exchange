#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Documentation JSON Generator for Commands - Generates JSON documentation from command classes
for use in the web interface.
"""

import os
import importlib
import inspect
import pkgutil
import sys
import json
from pathlib import Path
from datetime import datetime

# Add the source directory so the script works from a repository checkout.
root_dir = Path(__file__).resolve().parents[2]
source_dir = root_dir / "src"
sys.path.insert(0, str(source_dir))

try:
    from qzx.core.command_base import CommandBase
except ImportError:
    print("Error: Cannot import CommandBase. Make sure you're running this from the project root.")
    sys.exit(1)

# Output file paths
OUTPUT_FILE = os.path.join(root_dir, "WebsiteQZX", "public", "data", "commands.json")
LLMS_TXT_FILE = os.path.join(root_dir, "WebsiteQZX", "public", "llms.txt")

def generate_llms_txt(categories):
    """Generates the content for llms.txt containing all commands dynamically"""
    lines = [
        "# QZX - Quick Zap Exchange",
        "> Verbose is Gold. Consistent cross-platform CLI diagnostics.",
        "",
        "QZX is a cross-platform command-line tool designed to provide identical outputs and JSON formatting across Windows, macOS, and Linux.",
        "",
        "## Philosophy: Verbose is Gold",
        "Traditional Unix commands favor silence on success. QZX operates under the **\"Verbose is Gold\"** philosophy: every command returns a structured JSON payload with rich metadata and human-readable context. Responses always contain at least:",
        "```json",
        "{",
        '  "success": true,',
        '  "message": "Descriptive status message",',
        '  "details": { ... extra records ... }',
        "}",
        "```",
        "",
        "---",
        "",
        "## Installation & Usage",
        "",
        "### CLI Installation",
        "Install globally using npm/pnpm:",
        "```bash",
        "npm install -g qzx-cli",
        "# or",
        "pnpm add -g qzx-cli",
        "```",
        "",
        "### Basic Syntax",
        "```bash",
        "qzx <command> [arguments] [options]",
        "```",
        "Add `--json` anywhere in the command arguments to force raw JSON output (optimal for AI agents and automation scripts).",
        "",
        "---",
        "",
        "## Complete Command Index",
        ""
    ]

    # Map categories to their display names and emoji
    category_map = {
        'file': '📁 File Commands',
        'network': '🌐 Network Commands',
        'system': '💻 System Commands',
        'dev': '🛠️ Development Commands',
        'development': '🛠️ Development Commands'
    }

    # Normalize category grouping
    grouped_cmds = {}
    for cat_name, cmd_classes in categories.items():
        normalized_cat = 'development' if cat_name == 'dev' else cat_name
        if normalized_cat not in grouped_cmds:
            grouped_cmds[normalized_cat] = []
        grouped_cmds[normalized_cat].extend(cmd_classes)

    # Output categories in a specific order: file, network, system, development
    for cat_key in ['file', 'network', 'system', 'development']:
        if cat_key not in grouped_cmds:
            continue
        
        display_title = category_map.get(cat_key, f"{cat_key.capitalize()} Commands")
        lines.append(f"### {display_title}")
        
        # Sort commands by name
        sorted_cmds = sorted(grouped_cmds[cat_key], key=lambda c: c.name)
        for cmd_class in sorted_cmds:
            # Build parameter list string
            param_parts = []
            if cmd_class.parameters:
                for param in cmd_class.parameters:
                    name = param.get('name', 'unnamed')
                    required = param.get('required', False)
                    if required:
                        param_parts.append(f"<{name}>")
                    else:
                        param_parts.append(f"[{name}]")
            
            param_str = " " + " ".join(param_parts) if param_parts else ""
            desc = cmd_class.description or "No description"
            
            lines.append(f"*   **`{cmd_class.name}`**{param_str} - {desc}")
            
            # If there are aliases, append them
            if cmd_class.aliases:
                aliases_str = ", ".join([f"`{alias}`" for alias in cmd_class.aliases])
                lines.append(f"    *Aliases: {aliases_str}*")
                
        lines.append("")

    lines.extend([
        "---",
        "",
        "For full details, interactive demos, and documentation, visit: https://qzx.yumbale.com",
        ""
    ])

    return "\n".join(lines)


def get_commands_directories():
    """Returns a list of directories that contain commands"""
    commands_dir = os.path.join(source_dir, "qzx", "commands")
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
        package_name = os.path.relpath(commands_dir, source_dir).replace(os.path.sep, '.')
        
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

def group_by_category(command_classes):
    """Groups command classes by their category"""
    categories = {}
    
    for cmd_class in command_classes:
        category = cmd_class.category
        if category not in categories:
            categories[category] = []
        categories[category].append(cmd_class)
    
    return categories

def command_to_json(cmd_class):
    """Converts a command class to a JSON-serializable dictionary"""
    # Extract class docstring
    class_doc = inspect.getdoc(cmd_class)
    
    # Extract execute method docstring
    execute_doc = ""
    if hasattr(cmd_class, 'execute'):
        execute_doc = inspect.getdoc(cmd_class.execute)
    
    # Format parameters
    formatted_params = []
    if cmd_class.parameters:
        for param in cmd_class.parameters:
            formatted_params.append({
                'name': param.get('name', 'unnamed'),
                'description': param.get('description', 'No description'),
                'required': param.get('required', False),
                'default': param.get('default', None)
            })
    
    # Format examples
    formatted_examples = []
    if cmd_class.examples:
        for example in cmd_class.examples:
            formatted_examples.append({
                'command': example.get('command', ''),
                'description': example.get('description', 'No description')
            })
    
    # Build the JSON object
    result = {
        'name': cmd_class.name,
        'category': cmd_class.category,
        'description': cmd_class.description,
        'aliases': cmd_class.aliases if cmd_class.aliases else [],
        'parameters': formatted_params,
        'examples': formatted_examples,
        'class_doc': class_doc,
        'execute_doc': execute_doc,
        'module': cmd_class.__module__
    }
    
    return result

def generate_json(categories):
    """Generates a JSON structure for all commands"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Initialize the result structure
    result = {
        'metadata': {
            'generated_on': timestamp,
            'generator': 'generate_command_json.py'
        },
        'categories': {},
        'commands': {}
    }
    
    # Process each category
    for category, commands in categories.items():
        # Add to categories structure
        result['categories'][category] = {
            'name': category,
            'display_name': category.capitalize(),
            'commands': [cmd.name for cmd in commands]
        }
        
        # Add each command
        for cmd in commands:
            result['commands'][cmd.name] = command_to_json(cmd)
    
    return result

def ensure_output_directory():
    """Ensures the output directory exists"""
    output_dir = os.path.dirname(OUTPUT_FILE)
    if not os.path.exists(output_dir):
        print(f"Creating output directory: {output_dir}")
        os.makedirs(output_dir, exist_ok=True)

def main():
    print("Generating commands JSON documentation...")
    print(f"Working directory: {os.getcwd()}")
    print(f"Script location: {os.path.dirname(os.path.abspath(__file__))}")
    print(f"Root directory: {root_dir}")
    print(f"Output file path: {OUTPUT_FILE}")
    
    try:
        # Ensure output directory exists
        ensure_output_directory()
        
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
        
        # Generate JSON structure
        print("Generating JSON structure...")
        json_data = generate_json(categories)
        
        # Write to file
        print(f"Writing to {OUTPUT_FILE}...")
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)
        
        print(f"JSON documentation successfully written to {OUTPUT_FILE}")
        
        # Write to llms.txt
        llms_data = generate_llms_txt(categories)
        print(f"Writing to {LLMS_TXT_FILE}...")
        with open(LLMS_TXT_FILE, 'w', encoding='utf-8') as f:
            f.write(llms_data)
        
        print(f"llms.txt successfully written to {LLMS_TXT_FILE}")
    
    except Exception as e:
        print(f"Error generating JSON documentation: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 
