#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
QZX Core - The core engine for the QZX command system
"""

import os
import sys
import importlib
import inspect
import pkgutil
import platform
from importlib import import_module

# Define base command class that will be used for type checking
class QZXCommand:
    """Base class for all QZX commands"""
    
    name = "base"  # Command name for registration
    description = "Base command class"  # Command description
    
    def __init__(self, qzx_core):
        """Initialize the command with a reference to the core"""
        self.qzx_core = qzx_core
    
    def execute(self, *args):
        """Execute the command with the given arguments"""
        raise NotImplementedError("Command must implement execute method")

class QZXCore:
    """Core engine for the QZX command system"""
    
    def __init__(self):
        """Initialize the QZX core engine"""
        self.version = "0.02"  # Updated version for modular system
        self.os_type = platform.system().lower()
        self.commands = {}  # Dictionary to store command instances
        
        # Load all available commands
        self._load_commands()
    
    def _load_commands(self):
        """Dynamically load all available commands from the Commands directory"""
        commands_package = 'Commands'
        
        # Ensure the Commands directory is in the Python path
        if not os.path.isdir(commands_package):
            print(f"Warning: Commands directory not found at {os.path.abspath(commands_package)}")
            return
        
        # Add current directory to sys.path if not already there
        current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if current_dir not in sys.path:
            sys.path.insert(0, current_dir)
        
        try:
            # Import the Commands package
            commands_module = import_module(commands_package)
            
            # Find all modules in the Commands package
            for _, module_name, is_pkg in pkgutil.iter_modules(
                commands_module.__path__, commands_module.__name__ + '.'
            ):
                if is_pkg:
                    continue  # Skip subpackages for now
                
                # Import the module
                try:
                    module = importlib.import_module(module_name)
                    
                    # Find all classes in the module that inherit from QZXCommand
                    for name, obj in inspect.getmembers(module):
                        if (inspect.isclass(obj) and 
                            issubclass(obj, QZXCommand) and 
                            obj is not QZXCommand):
                            
                            # Create instance of the command
                            cmd_instance = obj(self)
                            
                            # Register the command with its name
                            self.commands[cmd_instance.name.lower()] = cmd_instance
                            # Solo mostrar mensaje de registro si se solicita (--verbose o similar)
                            if len(sys.argv) > 2 and '--verbose' in sys.argv:
                                print(f"Registered command: {cmd_instance.name}")
                
                except (ImportError, AttributeError) as e:
                    print(f"Error loading module {module_name}: {str(e)}")
        
        except ImportError as e:
            print(f"Error loading commands package: {str(e)}")
    
    def execute(self, command_name, args):
        """Execute the specified command with the given arguments"""
        command_name = command_name.lower()
        
        # Find the command (case-insensitive)
        for cmd_name, cmd_instance in self.commands.items():
            if cmd_name.lower() == command_name:
                return cmd_instance.execute(*args)
        
        return f"Error: Command '{command_name}' not found"
    
    def get_version(self):
        """Get the current version of QZX"""
        return self.version
    
    def get_os_type(self):
        """Get the current operating system type"""
        return self.os_type
    
    def get_command_list(self):
        """Get a list of all available commands"""
        return sorted(self.commands.keys()) 