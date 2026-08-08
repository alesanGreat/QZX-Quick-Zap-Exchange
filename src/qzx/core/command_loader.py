#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
QZX Command Loader - Handles loading commands from various modules
"""

import importlib
import sys
from .command_base import CommandBase
from .command_index import (
    CommandIndexError,
    indexed_command,
    indexed_command_names,
    indexed_command_records,
    validate_command_index_inventory,
    validate_loaded_command,
)

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
    
    def discover_commands(self, validate_index=True):
        """
        Discover and load all command classes from the command paths
        
        Returns:
            Dict of commands mapped by their names (lowercase)
        """
        if self._discovered:
            return self.commands

        # Keep this standard-library import off the one-command hot path while
        # making full discovery self-contained for generators and CI.
        import pkgutil

        self.command_packages = self._discover_command_packages()

        for package_name in self.command_packages:
            package = importlib.import_module(package_name)
            for module in pkgutil.iter_modules(package.__path__):
                if not module.ispkg and not module.name.startswith("_"):
                    self._load_command_from_module(f"{package_name}.{module.name}")

        from .command_lifecycle import (
            CommandLifecycleError,
            validate_lifecycle_inventory,
        )

        try:
            validate_lifecycle_inventory(
                command_class.name
                for command_class in set(self.commands.values())
            )
        except CommandLifecycleError as exc:
            if not self.load_errors:
                raise
            raise self._lifecycle_error_with_load_context(exc) from exc
        if validate_index:
            validate_command_index_inventory(set(self.commands.values()))
        self._discovered = True
        return self.commands

    def _discover_command_packages(self):
        """Return command category packages without importing their modules."""
        import pkgutil

        if self.command_packages:
            return self.command_packages
        commands_package = importlib.import_module("qzx.commands")
        self.command_packages = sorted(
            module.name
            for module in pkgutil.iter_modules(
                commands_package.__path__,
                commands_package.__name__ + ".",
            )
            if module.ispkg and not module.name.rsplit(".", 1)[-1].startswith("_")
        )
        return self.command_packages

    def _lifecycle_error_with_load_context(self, lifecycle_error):
        """Attach suppressed module import failures to inventory errors."""
        from .command_lifecycle import CommandLifecycleError

        failures = "; ".join(
            "{} [{}]: {}".format(
                module_name,
                details["type"],
                details["message"],
            )
            for module_name, details in sorted(self.load_errors.items())
        )
        return CommandLifecycleError(
            "{} Command modules that failed to load: {}.".format(
                lifecycle_error,
                failures or "none recorded",
            )
        )
    
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
        import re

        # Common pattern for ImportError messages: "No module named 'X'"
        match = re.search(r"No module named '?([a-zA-Z0-9_\.-]+)'?", error_message)
        if match:
            return match.group(1)
        return None

    def _load_indexed_command(self, entry):
        """Import and register exactly one class named by the validated index."""
        module_name = entry["module"]
        try:
            module = importlib.import_module(module_name)
        except ImportError as exc:
            error_msg = str(exc)
            self.load_errors[module_name] = {
                "type": "ImportError",
                "message": error_msg,
                "missing_dependency": self._extract_missing_module_name(
                    error_msg
                ),
            }
            return None
        except Exception as exc:
            self.load_errors[module_name] = {
                "type": type(exc).__name__,
                "message": str(exc),
                "missing_dependency": None,
            }
            return None

        self.command_modules[module_name] = module
        command_class = getattr(module, entry["class_name"], None)
        if (
            not isinstance(command_class, type)
            or not issubclass(command_class, CommandBase)
            or command_class is CommandBase
            or command_class.__module__ != module.__name__
        ):
            raise CommandIndexError(
                "Indexed command '{}' does not resolve to the declared "
                "CommandBase subclass '{}.{}'.".format(
                    entry["name"],
                    module_name,
                    entry["class_name"],
                )
            )

        validate_loaded_command(entry, command_class)
        normalized = entry["name"].lower()
        existing = self.commands.get(normalized)
        if existing is not None and existing is not command_class:
            raise CommandIndexError(
                "Indexed command '{}' conflicts with a command already "
                "loaded from '{}'.".format(
                    entry["name"],
                    existing.__module__,
                )
            )
        self.commands[normalized] = command_class
        return command_class
    
    def _load_command_from_module(self, module_name):
        """
        Load commands from a specific module
        
        Args:
            module_name: Fully qualified module name
        """
        import inspect

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
        # Always convert to lowercase to ensure case-insensitivity
        command_name = command_name or ""
        normalized_name = command_name.lower()
        command_class = self.commands.get(normalized_name)
        if command_class is None and not self._discovered:
            entry = indexed_command(command_name)
            if entry is None:
                return None
            self._load_indexed_command(entry)
            module_error = self.load_errors.get(entry["module"])
            if module_error is not None:
                raise CommandIndexError(
                    "Indexed command '{}' could not load module '{}': {}: {}.".format(
                        entry["name"],
                        entry["module"],
                        module_error["type"],
                        module_error["message"],
                    )
                )
            command_class = self.commands.get(normalized_name)
            if command_class is None:
                raise CommandIndexError(
                    "Indexed lookup '{}' was not registered after importing '{}'.".format(
                        command_name,
                        entry["module"],
                    )
                )
        if command_class:
            return command_class()
        return None

    def get_all_commands(self):
        """Return all registered commands, discovering them on first use."""
        if not self._discovered:
            self.discover_commands()
        return self.commands

    def get_command_maturity(self, command_name):
        """Return lifecycle details for a canonical command name."""
        from .command_lifecycle import command_maturity

        entry = indexed_command(command_name)
        if entry is None:
            return None
        return command_maturity(entry["name"])

    def suggest_command_names(self, command_name, limit=5, cutoff=0.5):
        """Return close canonical command names without importing commands."""
        import difflib

        normalized_name = str(command_name or "").lower()
        canonical_by_normalized = {
            name.lower(): name
            for name in self.get_known_command_names()
        }
        matches = difflib.get_close_matches(
            normalized_name,
            sorted(canonical_by_normalized),
            n=max(0, int(limit)),
            cutoff=float(cutoff),
        )
        return [canonical_by_normalized[name] for name in matches]

    def get_indexed_commands(self):
        """Return canonical metadata without importing command modules."""
        return indexed_command_records()

    def get_known_command_names(self):
        """Return canonical lookup names without full discovery."""
        return indexed_command_names()
    
    def list_commands(self):
        """
        List all available commands
        
        Returns:
            List of (command_name, description, category) tuples
        """
        result = [
            (entry["name"], entry["description"], entry["category"])
            for entry in indexed_command_records()
        ]
        
        # Sort by category and then by name
        return sorted(result, key=lambda x: (x[2], x[0])) 
