#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
WonderIfDirectoryEmpty Command - Checks if a directory is empty
"""

import os
from Core.command_base import CommandBase

class WonderIfDirectoryEmptyCommand(CommandBase):
    """
    Command to check if a directory is empty
    """
    
    name = "wonderIfDirectoryEmpty"
    description = "Checks if a directory is empty (contains no files or subdirectories)"
    category = "file"
    
    parameters = [
        {
            'name': 'directory_path',
            'description': 'Path to the directory to check',
            'required': True
        },
        {
            'name': 'include_hidden',
            'description': 'Whether to include hidden files in the check',
            'required': False,
            'default': False
        }
    ]
    
    examples = [
        {
            'command': 'qzx wonderIfDirectoryEmpty /path/to/directory',
            'description': 'Check if /path/to/directory is empty, ignoring hidden files'
        },
        {
            'command': 'qzx wonderIfDirectoryEmpty /path/to/directory true',
            'description': 'Check if /path/to/directory is empty, including hidden files'
        }
    ]
    
    def execute(self, directory_path, include_hidden=False):
        """
        Checks if a directory is empty
        
        Args:
            directory_path (str): Path to the directory to check
            include_hidden (bool, optional): Whether to include hidden files in the check
            
        Returns:
            Dictionary with the result of the check
        """
        try:
            # Validate directory exists
            if not os.path.exists(directory_path):
                return {
                    "success": False,
                    "error": f"Directory '{directory_path}' does not exist"
                }
            
            # Validate it's a directory
            if not os.path.isdir(directory_path):
                return {
                    "success": False,
                    "error": f"'{directory_path}' is not a directory"
                }
            
            # Convert include_hidden to boolean if it's a string
            if isinstance(include_hidden, str):
                include_hidden = include_hidden.lower() in ('true', 'yes', 'y', '1')
            
            # Get directory contents
            contents = os.listdir(directory_path)
            
            # If we don't want to include hidden files, filter them out
            if not include_hidden:
                contents = [item for item in contents if not item.startswith('.')]
            
            # Check if it's empty
            is_empty = len(contents) == 0
            
            # Prepare result
            result = {
                "success": True,
                "directory_path": os.path.abspath(directory_path),
                "is_empty": is_empty,
                "include_hidden": include_hidden
            }
            
            # Add more detailed information
            if not is_empty:
                result["item_count"] = len(contents)
                result["file_count"] = sum(1 for item in contents if os.path.isfile(os.path.join(directory_path, item)))
                result["directory_count"] = sum(1 for item in contents if os.path.isdir(os.path.join(directory_path, item)))
            
            # Add a message
            if is_empty:
                result["message"] = f"Directory '{directory_path}' is empty"
            else:
                result["message"] = f"Directory '{directory_path}' is not empty (contains {result['item_count']} items: {result['file_count']} files, {result['directory_count']} directories)"
            
            return result
        
        except Exception as e:
            return {
                "success": False,
                "directory_path": directory_path,
                "error": str(e)
            } 