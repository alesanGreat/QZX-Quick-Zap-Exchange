#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
QZX Command Loader - Handles loading commands from various modules
"""

import importlib
import inspect
import pkgutil
import re
import sys
from .command_base import CommandBase

class CommandLoader:
    """
    Loads command classes from specified directories and manages them
    """
    
    def __init__(self):
        """
        Initialize the command loader
        """
        self.commands = {}
        self.command_modules = {}
        self.command_packages = []
        self.load_errors = {}
        self.registration_warnings = []
        self._discovered = False
        # Retained for backwards-compatible diagnostics. Runtime installation
        # is intentionally disabled.
        self.attempted_installs = set()
    
    def discover_commands(self):
        """
        Discover and load all command classes from the command paths
        
        Returns:
            Dict of commands mapped by their names (lowercase)
        """
        if self._discovered:
            return self.commands

        commands_package = importlib.import_module("qzx.commands")
        self.command_packages = sorted(
            module.name
            for module in pkgutil.iter_modules(
                commands_package.__path__,
                commands_package.__name__ + ".",
            )
            if module.ispkg and not module.name.rsplit(".", 1)[-1].startswith("_")
        )

        for package_name in self.command_packages:
            package = importlib.import_module(package_name)
            for module in pkgutil.iter_modules(package.__path__):
                if not module.ispkg and not module.name.startswith("_"):
                    self._load_command_from_module(f"{package_name}.{module.name}")

        self._discovered = True
        return self.commands
    
    def _try_install_module(self, module_name):
        """
        Attempts to install a missing module using pip
        
        Args:
            module_name: Name of the module to install
            
        Returns:
            bool: True if installation was successful, False otherwise
        """
        # Installing packages while merely listing or executing another command
        # is unsafe and makes startup nondeterministic. Optional dependencies
        # must be installed explicitly by the user or through package extras.
        self.attempted_installs.add(module_name)
        return False
    
    def _extract_missing_module_name(self, error_message):
        """
        Extracts the missing module name from an ImportError message
        
        Args:
            error_message: The error message string
            
        Returns:
            str: The name of the missing module, or None if not found
        """
        # Common pattern for ImportError messages: "No module named 'X'"
        match = re.search(r"No module named '?([a-zA-Z0-9_\.-]+)'?", error_message)
        if match:
            return match.group(1)
        return None
    
    def _load_command_from_module(self, module_name):
        """
        Load commands from a specific module
        
        Args:
            module_name: Fully qualified module name
        """
        try:
            # Import the module
            module = importlib.import_module(module_name)
            self.command_modules[module_name] = module
            
            # Find all command classes in the module
            for name, obj in inspect.getmembers(module):
                # Check if it's a class that inherits from CommandBase and is not CommandBase itself
                if (inspect.isclass(obj) and 
                    issubclass(obj, CommandBase) and 
                    obj is not CommandBase and
                    obj.__module__ == module.__name__):
                    
                    # Instantiate the command
                    command_instance = obj()
                    
                    # Get the command name and ensure it's lowercase for case-insensitive lookup
                    command_name = command_instance.name.lower()
                    
                    existing = self.commands.get(command_name)
                    if existing is not None and existing is not obj:
                        warning = (
                            "Duplicate canonical command '{}': {} conflicts with {}"
                        ).format(
                            command_instance.name,
                            obj.__module__,
                            existing.__module__,
                        )
                        self.registration_warnings.append(warning)
                        continue

                    # Register the command by its lowercase name
                    self.commands[command_name] = obj
                    
                    # Handle aliases if present
                    if hasattr(command_instance, 'aliases') and command_instance.aliases:
                        for alias in command_instance.aliases:
                            alias_lower = alias.lower()
                            if alias_lower == command_name:
                                continue
                            # Never let an alias replace a command registered earlier.
                            existing_alias = self.commands.get(alias_lower)
                            if existing_alias is not None and existing_alias is not obj:
                                self.registration_warnings.append(
                                    "Alias '{}' from {} conflicts with {}".format(
                                        alias,
                                        obj.__module__,
                                        existing_alias.__module__,
                                    )
                                )
                                continue
                            self.commands[alias_lower] = obj
                            # Solo mostrar mensaje de alias si se solicita (--verbose o similar)
                            if len(sys.argv) > 2 and '--verbose' in sys.argv:
                                print(f"Registered alias: {alias_lower} -> {command_name} ({module_name})")
                    
                    # Print registration info solo en modo verbose
                    if len(sys.argv) > 2 and '--verbose' in sys.argv:
                        print(f"Registered command: {command_name} ({module_name})")
        except ImportError as e:
            error_msg = str(e)
            self.load_errors[module_name] = {
                "type": "ImportError",
                "message": error_msg,
                "missing_dependency": self._extract_missing_module_name(error_msg),
            }
            
            if "--verbose" in sys.argv:
                print(
                    "Import error loading module {}: {}".format(
                        module_name,
                        error_msg,
                    ),
                    file=sys.stderr,
                )
        except Exception as e:
            self.load_errors[module_name] = {
                "type": type(e).__name__,
                "message": str(e),
                "missing_dependency": None,
            }
            if "--verbose" in sys.argv:
                print(
                    "Error loading module {}: {}".format(module_name, str(e)),
                    file=sys.stderr,
                )
    
    def get_command(self, command_name):
        """
        Get a command by name (case-insensitive)
        
        Args:
            command_name: Name of the command to get
            
        Returns:
            Command instance or None if not found
        """
        if not self.commands:
            self.discover_commands()

        # Always convert to lowercase to ensure case-insensitivity
        command_name = command_name.lower() if command_name else ""
        
        command_class = self.commands.get(command_name)
        if command_class:
            return command_class()
        return None

    def get_all_commands(self):
        """Return all registered commands, discovering them on first use."""
        if not self.commands:
            self.discover_commands()
        return self.commands
    
    def list_commands(self):
        """
        List all available commands
        
        Returns:
            List of (command_name, description, category) tuples
        """
        if not self.commands:
            self.discover_commands()

        result = [
            (instance.name, instance.description, instance.category)
            for instance in (
                command_class() for command_class in set(self.commands.values())
            )
        ]
        
        # Sort by category and then by name
        return sorted(result, key=lambda x: (x[2], x[0])) 
