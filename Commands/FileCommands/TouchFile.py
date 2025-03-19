#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
TouchFile Command - Creates an empty file or updates the timestamp of an existing file
"""

import os
from Core.command_base import CommandBase

class TouchFileCommand(CommandBase):
    """
    Command to create an empty file or update the timestamp of an existing file
    """
    
    name = "touchFile"
    description = "Creates an empty file or updates the timestamp of an existing file"
    category = "file"
    
    parameters = [
        {
            'name': 'path',
            'description': 'Path to the file to create or update',
            'required': True
        },
        {
            'name': 'create_dirs',
            'description': 'Whether to create parent directories if they do not exist',
            'required': False,
            'default': False
        },
        {
            'name': 'content',
            'description': 'Content to write to the file',
            'required': False,
            'default': ''
        }
    ]
    
    examples = [
        {
            'command': 'qzx touchFile newfile.txt',
            'description': 'Create an empty file or update its timestamp'
        },
        {
            'command': 'qzx touchFile dir/newfile.txt true',
            'description': 'Create a file and its parent directories if they do not exist'
        },
        {
            'command': 'qzx touchFile file.txt false "Hello World"',
            'description': 'Create a file with content or update an existing file'
        }
    ]
    
    def execute(self, path, create_dirs=False, content=''):
        """
        Creates an empty file or updates the timestamp of an existing file
        
        Args:
            path (str): Path to the file to create or update
            create_dirs (bool, optional): Whether to create parent directories if they do not exist
            content (str, optional): Content to write to the file
            
        Returns:
            Operation result
        """
        try:
            # Convert create_dirs to boolean if it's a string
            if isinstance(create_dirs, str):
                create_dirs = create_dirs.lower() in ('true', 'yes', 'y', '1')
            
            # Get the directory part of the path
            dir_path = os.path.dirname(path)
            
            # Create parent directories if requested
            if dir_path and create_dirs and not os.path.exists(dir_path):
                os.makedirs(dir_path)
            
            # Prepare the result
            result = {
                "path": os.path.abspath(path),
                "success": True
            }
            
            # Check if file already exists
            file_existed = os.path.exists(path)
            
            # Open the file in the appropriate mode ('a' for append, which will
            # create the file if it doesn't exist or just update the timestamp if it does)
            mode = 'w' if content else 'a'
            with open(path, mode) as f:
                if content:
                    f.write(content)
            
            # Get file info after operation
            file_size = os.path.getsize(path)
            file_mode = oct(os.stat(path).st_mode)[-3:]
            
            # Add information to result
            result.update({
                "existed": file_existed,
                "created": not file_existed,
                "size": file_size,
                "mode": file_mode,
                "content_added": bool(content)
            })
            
            # Set appropriate message
            if file_existed:
                if content:
                    result["message"] = f"File '{path}' updated with new content"
                else:
                    result["message"] = f"File '{path}' timestamp updated"
            else:
                if content:
                    result["message"] = f"File '{path}' created with content"
                else:
                    result["message"] = f"Empty file '{path}' created"
            
            return result
        except Exception as e:
            return {
                "success": False,
                "path": path,
                "error": str(e)
            }
    
    def _format_bytes(self, bytes_value):
        """
        Format bytes to a human-readable format
        
        Args:
            bytes_value (int): Bytes to format
            
        Returns:
            str: Formatted string with the appropriate unit
        """
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_value < 1024 or unit == 'TB':
                return f"{bytes_value:.2f} {unit}"
            bytes_value /= 1024