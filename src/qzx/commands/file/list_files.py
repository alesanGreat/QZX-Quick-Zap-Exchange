#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ListFiles Command - Lists files in a directory with support for wildcards and recursive searching
Using the centralized recursive file finder utility
"""

from qzx.commands.file._list_files_workflow import execute_list_files
from qzx.core.command_base import CommandBase

class ListFilesCommand(CommandBase):
    """
    Command to list files in a directory with support for wildcards and recursive searching
    
    Supports flags:
    -r, -R, --recursive: Enable unlimited recursive directory search
    -rN, --recursiveN: Enable recursive directory search up to N levels deep
    
    This version uses the centralized recursive file finder utility.
    """
    
    name = "listFiles"
    description = "Lists files in a directory with support for wildcards and recursive searching"
    category = "file"
    
    parameters = [
        {
            'name': 'directory_path',
            'description': 'Path to the directory to list files from',
            'required': False,
            'default': '.'
        },
        {
            'name': 'pattern',
            'description': 'File pattern to filter by (e.g., "*.txt", "doc*.pdf")',
            'required': False,
            'default': '*'
        },
        {
            'name': 'recursive',
            'description': 'Recursion level: none by default, -r/--recursive for unlimited depth, -rN/--recursiveN for N levels deep',
            'required': False,
            'default': None
        }
    ]
    
    examples = [
        {
            'command': 'qzx listFiles',
            'description': 'List all files in the current directory'
        },
        {
            'command': 'qzx listFiles C:\\Documents',
            'description': 'List all files in the C:\\Documents directory (Windows)'
        },
        {
            'command': 'qzx listFiles /home/user/documents',
            'description': 'List all files in the /home/user/documents directory (Linux/Mac)'
        },
        {
            'command': 'qzx listFiles . "*.py"',
            'description': 'List all Python files in the current directory'
        },
        {
            'command': 'qzx listFiles src "*.js" -r',
            'description': 'List all JavaScript files in the src directory and all its subdirectories'
        },
        {
            'command': 'qzx listFiles src "*.js" -r2',
            'description': 'List all JavaScript files in the src directory and up to 2 levels of subdirectories'
        }
    ]
    
    def execute(self, directory_path=".", pattern="*", recursive=None):
        """List matching files and directories using the centralized finder."""
        return execute_list_files(self, directory_path, pattern, recursive)

    def _format_size(self, size_bytes):
        """
        Format a size in bytes to a human-readable string
        
        Args:
            size_bytes (int): Size in bytes
            
        Returns:
            str: Formatted size string (e.g., "1.23 MB")
        """
        if size_bytes == 0:
            return "0 B"
            
        # Define units and their corresponding sizes
        units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
        unit_index = 0
        current_size = float(size_bytes)
        
        # Find the appropriate unit
        while current_size >= 1024 and unit_index < len(units) - 1:
            current_size /= 1024
            unit_index += 1
            
        # Format the size with appropriate precision
        if current_size < 10:
            # For small numbers, show 2 decimal places
            return f"{current_size:.2f} {units[unit_index]}"
        elif current_size < 100:
            # For medium numbers, show 1 decimal place
            return f"{current_size:.1f} {units[unit_index]}"
        else:
            # For large numbers, show no decimal places
            return f"{int(current_size)} {units[unit_index]}" 
