#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Welcome Command - Displays the system welcome information
"""

import os
import sys
from Core.command_base import CommandBase

# Import the welcome module
from Commands.SystemCommands.TerminalWelcome import TerminalWelcome

class WelcomeCommand(CommandBase):
    """
    Command to display the system welcome information
    """
    
    name = "Welcome"
    aliases = ["welcome", "hello", "hi"]
    description = "Displays the welcome screen with system information"
    category = "system"
    
    parameters = [
        {
            'name': 'full_info',
            'description': 'Show full system information (true/false)',
            'required': False,
            'default': 'true'
        }
    ]
    
    examples = [
        {
            'command': 'qzx Welcome',
            'description': 'Display the welcome screen with full system information'
        },
        {
            'command': 'qzx Welcome false',
            'description': 'Display the basic welcome screen without detailed information'
        }
    ]
    
    def execute(self, full_info="true"):
        """
        Display the welcome screen with system information
        
        Args:
            full_info (str): Whether to show full information ('true' or 'false')
            
        Returns:
            Dictionary with the operation result
        """
        try:
            # Convert parameter to boolean
            if isinstance(full_info, str):
                show_full_info = full_info.lower() in ('true', 'yes', 'y', '1', 't')
            else:
                show_full_info = bool(full_info)
            
            # Get the QZX version
            qzx_version = "0.02"  # Default, could be obtained dynamically
            
            # Instantiate the welcome generator
            welcome_generator = TerminalWelcome(qzx_version=qzx_version)
            
            # Get the formatted message
            welcome_message = welcome_generator.get_welcome_message(show_full_info=show_full_info)
            
            # Create a detailed description of what was displayed
            info_level = "detailed" if show_full_info else "basic"
            message = f"QZX Welcome screen ({info_level} view) displayed successfully. Version {qzx_version}."
            
            # If we're in the terminal, return the message for display
            if hasattr(self, 'in_terminal') and self.in_terminal:
                return {
                    "success": True,
                    "message": message,
                    "output": welcome_message,
                    "info_level": info_level,
                    "qzx_version": qzx_version
                }
            
            # Otherwise, print the message directly
            print(welcome_message)
            
            return {
                "success": True,
                "message": message,
                "welcome_displayed": True,
                "info_level": info_level,
                "qzx_version": qzx_version
            }
            
        except Exception as e:
            error_message = f"Error displaying welcome screen: {str(e)}"
            return {
                "success": False,
                "error": error_message,
                "message": f"Failed to display QZX welcome screen: {str(e)}",
                "welcome_displayed": False
            } 