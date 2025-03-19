#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
CurrentDir Command - Shows the current working directory
"""

import os
from Core.command_base import CommandBase

class CurrentDirCommand(CommandBase):
    """
    Command to show the current directory where QZX is running
    """
    
    name = "CurrentDir"
    aliases = ["pwd", "cwd", "dir", "where", "location"]  # Various aliases in English
    description = "Shows the current working directory"
    category = "system"
    
    parameters = [
        {
            'name': 'full',
            'description': 'Show full path (true) or relative path (false)',
            'required': False,
            'default': 'true'
        }
    ]
    
    examples = [
        {
            'command': 'qzx CurrentDir',
            'description': 'Shows the full current working directory'
        },
        {
            'command': 'qzx pwd',
            'description': 'Alias that shows the current working directory'
        },
        {
            'command': 'qzx dir false',
            'description': 'Shows only the current directory name without the full path'
        }
    ]
    
    def execute(self, full='true'):
        """
        Shows the current directory where QZX is running
        
        Args:
            full (str, optional): Show full path ('true') or just the directory name ('false')
            
        Returns:
            Dictionary with the operation result and status
        """
        try:
            # Convert parameter to boolean
            if isinstance(full, str):
                full = full.lower() in ('true', 'yes', 'y', '1', 't')
            
            # Get current directory
            current_dir = os.getcwd()
            
            # Collect additional path information for more context
            parent_dir = os.path.dirname(current_dir)
            dir_name = os.path.basename(current_dir)
            home_dir = os.path.expanduser("~")
            
            # Check if the current directory is under the home directory
            in_home = current_dir.startswith(home_dir)
            home_relative = None
            if in_home:
                # Create a path that shows the relation to home directory
                home_relative = "~" + current_dir[len(home_dir):]
            
            # If full path is not required, get only the directory name
            displayed_dir = current_dir
            if not full:
                displayed_dir = dir_name
            
            # Create a detailed message about the current directory
            message = f"Current directory: {displayed_dir}"
            
            # Add extra details for a more verbose message
            if full:
                if home_relative:
                    message += f" (relative to home: {home_relative})"
            else:
                message += f" (full path: {current_dir})"
            
            # Prepare the result with all information
            result = {
                "success": True,
                "current_dir": current_dir,
                "full_path": full,
                "displayed_path": displayed_dir,
                "directory_name": dir_name,
                "parent_directory": parent_dir,
                "message": message
            }
            
            # Add home-relative path if available
            if home_relative:
                result["home_relative_path"] = home_relative
            
            # If we're in a terminal, add special formatting
            if hasattr(self, 'in_terminal') and self.in_terminal:
                result["output"] = f"\n📂 {displayed_dir}\n"
            
            return result
            
        except Exception as e:
            error_message = f"Error getting current directory: {str(e)}"
            return {
                "success": False,
                "error": error_message,
                "message": f"Failed to retrieve current directory information: {str(e)}"
            } 