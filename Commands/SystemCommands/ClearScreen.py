#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ClearScreen Command - Clears the terminal screen
"""

import os
import sys
import platform
from Core.command_base import CommandBase

class ClearScreenCommand(CommandBase):
    """
    Command to clear the terminal screen
    """
    
    name = "ClearScreen"
    aliases = ["cls", "clear", "clrscr"]
    description = "Clears the terminal screen"
    category = "system"
    
    parameters = []
    
    examples = [
        {
            'command': 'qzx ClearScreen',
            'description': 'Clear the terminal screen'
        },
        {
            'command': 'qzx cls',
            'description': 'Clear the terminal screen (using alias)'
        }
    ]
    
    def execute(self):
        """
        Clear the terminal screen
        
        Returns:
            Dictionary with the operation result
        """
        try:
            # Identify the operating system and use the appropriate command
            os_type = platform.system().lower()
            
            if os_type == 'windows':
                os.system('cls')
            else:  # For Linux, macOS, etc.
                os.system('clear')
            
            return {
                "success": True,
                "message": "Screen cleared successfully.",
                "screen_cleared": True
            }
            
        except Exception as e:
            error_message = f"Error clearing screen: {str(e)}"
            
            # Fallback method if the os.system method fails
            try:
                if os_type == 'windows':
                    print('\033[2J\033[H', end='')
                else:
                    print('\033c', end='')
                
                return {
                    "success": True,
                    "message": "Screen cleared using fallback method.",
                    "screen_cleared": True,
                    "warning": error_message
                }
            except:
                return {
                    "success": False,
                    "error": error_message,
                    "message": f"Failed to clear screen: {str(e)}",
                    "screen_cleared": False
                } 