#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
QZX Command Loader - Handles loading commands from various modules
"""

import os
import importlib
import inspect
import re
import subprocess
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
        self.command_paths = [
            "Commands/FileCommands",
            "Commands/SystemCommands",
            "Commands/DevCommands"
        ]
        # Track modules we've already tried to install to avoid repeated attempts
        self.attempted_installs = set()
    
    def discover_commands(self):
        """
        Discover and load all command classes from the command paths
        
        Returns:
            Dict of commands mapped by their names (lowercase)
        """
        # Get the root directory (assumes this file is in /Core)
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        for path in self.command_paths:
            full_path = os.path.join(root_dir, path)
            
            # Skip if directory doesn't exist
            if not os.path.exists(full_path):
                continue
                
            # Get all Python files in the directory
            for filename in os.listdir(full_path):
                if filename.endswith('.py') and not filename.startswith('__'):
                    module_name = f"{path.replace('/', '.')}.{filename[:-3]}"
                    self._load_command_from_module(module_name)
        
        return self.commands
    
    def _try_install_module(self, module_name):
        """
        Attempts to install a missing module using pip
        
        Args:
            module_name: Name of the module to install
            
        Returns:
            bool: True if installation was successful, False otherwise
        """
        # Skip if we've already tried to install this module
        if module_name in self.attempted_installs:
            return False
            
        self.attempted_installs.add(module_name)
        
        try:
            print(f"Attempting to install missing module: {module_name}")
            
            # Special case for 'magic' module on Windows
            package_name = module_name
            if module_name == 'magic' and os.name == 'nt':  # 'nt' is Windows
                package_name = 'python-magic-bin'
                print(f"Detected Windows OS, will install '{package_name}' instead of '{module_name}'")
            
            # Use subprocess to run pip install
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", package_name],
                capture_output=True,
                text=True,
                check=False  # Don't raise error on non-zero exit
            )
            
            if result.returncode == 0:
                print(f"Successfully installed module: {package_name}")
                return True
            else:
                print(f"Failed to install module {package_name}: {result.stderr}")
                return False
        except Exception as e:
            print(f"Error while trying to install {module_name}: {str(e)}")
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
                    obj is not CommandBase):
                    
                    # Instantiate the command
                    command_instance = obj()
                    
                    # Get the command name and ensure it's lowercase for case-insensitive lookup
                    command_name = command_instance.name.lower()
                    
                    # Register the command by its lowercase name
                    self.commands[command_name] = obj
                    
                    # Handle aliases if present
                    if hasattr(command_instance, 'aliases') and command_instance.aliases:
                        for alias in command_instance.aliases:
                            alias_lower = alias.lower()
                            # Register each alias pointing to the same command class
                            self.commands[alias_lower] = obj
                            # Solo mostrar mensaje de alias si se solicita (--verbose o similar)
                            if len(sys.argv) > 2 and '--verbose' in sys.argv:
                                print(f"Registered alias: {alias_lower} -> {command_name} ({module_name})")
                    
                    # Also register with original capitalization for backward compatibility
                    # but only if it's different from the lowercase version
                    if command_instance.name != command_name:
                        self.commands[command_instance.name] = obj
                    
                    # Print registration info solo en modo verbose
                    if len(sys.argv) > 2 and '--verbose' in sys.argv:
                        print(f"Registered command: {command_name} ({module_name})")
        except ImportError as e:
            error_msg = str(e)
            print(f"Import error loading module {module_name}: {error_msg}")
            
            # Try to extract the missing module name
            missing_module = self._extract_missing_module_name(error_msg)
            if missing_module:
                # Attempt to install the missing module
                if self._try_install_module(missing_module):
                    # If installation succeeded, try importing again
                    try:
                        # Import the module
                        module = importlib.import_module(module_name)
                        self.command_modules[module_name] = module
                        
                        print(f"Successfully loaded module {module_name} after installing dependency")
                        
                        # Now try to register the commands again
                        for name, obj in inspect.getmembers(module):
                            if (inspect.isclass(obj) and 
                                issubclass(obj, CommandBase) and 
                                obj is not CommandBase):
                                
                                # Instantiate the command
                                command_instance = obj()
                                
                                # Get command name and register
                                command_name = command_instance.name.lower()
                                self.commands[command_name] = obj
                                
                                # Also register with original capitalization
                                if command_instance.name != command_name:
                                    self.commands[command_instance.name] = obj
                                
                                # Handle aliases
                                if hasattr(command_instance, 'aliases') and command_instance.aliases:
                                    for alias in command_instance.aliases:
                                        self.commands[alias.lower()] = obj
                    except Exception as retry_error:
                        print(f"Failed to load module {module_name} even after installing dependency: {str(retry_error)}")
        except Exception as e:
            print(f"Error loading module {module_name}: {str(e)}")
    
    def get_command(self, command_name):
        """
        Get a command by name (case-insensitive)
        
        Args:
            command_name: Name of the command to get
            
        Returns:
            Command instance or None if not found
        """
        # Always convert to lowercase to ensure case-insensitivity
        command_name = command_name.lower() if command_name else ""
        
        command_class = self.commands.get(command_name)
        if command_class:
            return command_class()
        return None
    
    def list_commands(self):
        """
        List all available commands
        
        Returns:
            List of (command_name, description, category) tuples
        """
        result = []
        
        # Track which commands we've already added to avoid duplicates
        processed_commands = set()
        
        for name, cmd_class in self.commands.items():
            # Create an instance to get its properties
            cmd_instance = cmd_class()
            
            # Use a unique identifier for the command (class name)
            cmd_identifier = cmd_instance.__class__.__name__
            
            # Skip if we've already processed this command class
            if cmd_identifier in processed_commands:
                continue
            
            # Skip lowercase duplicates (if original capitalization exists)
            original_name = cmd_instance.name
            if name != original_name and name.lower() == original_name.lower():
                continue
            
            processed_commands.add(cmd_identifier)
            result.append((original_name, cmd_instance.description, cmd_instance.category))
        
        # Sort by category and then by name
        return sorted(result, key=lambda x: (x[2], x[0])) 