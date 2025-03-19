#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
WonderMyEnvironment Command - Displays detailed system environment information
"""

import os
import sys
import platform
import time
from Core.command_base import CommandBase

# Import the terminal welcome module to reuse its methods
from Commands.SystemCommands.TerminalWelcome import TerminalWelcome

class WonderMyEnvironmentCommand(CommandBase):
    """
    Command to display detailed system environment information
    """
    
    name = "WonderMyEnvironment"
    aliases = ["environment", "sysinfo", "systeminfo"]
    description = "Displays detailed information about the system environment"
    category = "system"
    
    parameters = [
        {
            'name': 'detailed',
            'description': 'Show additional detailed information (true/false)',
            'required': False,
            'default': 'true'
        }
    ]
    
    examples = [
        {
            'command': 'qzx WonderMyEnvironment',
            'description': 'Display full system environment information'
        },
        {
            'command': 'qzx WonderMyEnvironment false',
            'description': 'Display basic system environment information'
        }
    ]
    
    def execute(self, detailed="true"):
        """
        Display detailed system environment information
        
        Args:
            detailed (str): Whether to show detailed information ('true' or 'false')
            
        Returns:
            Dictionary with the operation result
        """
        try:
            # Convert parameter to boolean
            if isinstance(detailed, str):
                show_detailed = detailed.lower() in ('true', 'yes', 'y', '1', 't')
            else:
                show_detailed = bool(detailed)
            
            # Get the QZX version
            qzx_version = "0.02.1"  # Should match the current version
            
            print("Starting environment analysis...")
            print("This may take a moment, please wait...")
            
            # Create an instance of TerminalWelcome to reuse its methods
            print("Initializing system information modules...")
            welcome_manager = TerminalWelcome(qzx_version=qzx_version)
            print("Initialization complete.")
            
            # Get system information with feedback
            print("\nCollecting basic system information...")
            sys_info = welcome_manager._format_system_info()
            print("Basic system information collected.")
            
            print("\nAnalyzing memory usage patterns...")
            ram_info = welcome_manager._format_ram_info()
            print("Memory analysis complete.")
            
            print("\nScanning storage devices...")
            disk_info = welcome_manager._format_disk_info()
            print("Storage scan complete.")
            
            print("\nDetecting and analyzing graphics processing units...")
            gpu_info = welcome_manager._format_gpu_info()
            if gpu_info:
                print("GPU analysis complete.")
            else:
                print("No GPU information available or GPU analysis skipped.")
            
            print("\nCompiling final report...")
            
            # Format the environment information
            environment_info = f"""
=================================================================
SYSTEM ENVIRONMENT INFORMATION
=================================================================

SYSTEM INFORMATION:
{sys_info}

MEMORY:
{ram_info}

STORAGE:
{disk_info}
"""

            # Add GPU information if available
            if gpu_info:
                environment_info += f"""
DETECTED GPUs:
{gpu_info}
"""

            environment_info += """
=================================================================
"""
            print("Environment analysis complete!")
            
            # If we're in the terminal, return the message for display
            if hasattr(self, 'in_terminal') and self.in_terminal:
                return {
                    "success": True,
                    "message": "System environment information displayed successfully.",
                    "output": environment_info
                }
            
            # Otherwise, print the message directly
            print(environment_info)
            
            return {
                "success": True,
                "message": "System environment information displayed successfully.",
                "system_info": welcome_manager.system_info
            }
            
        except Exception as e:
            error_message = f"Error displaying system environment information: {str(e)}"
            return {
                "success": False,
                "error": error_message,
                "message": f"Failed to display system environment information: {str(e)}"
            } 