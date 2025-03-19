#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ReadFile Command - Reads and displays the content of a file
"""

import os
from Core.command_base import CommandBase

class ReadFileCommand(CommandBase):
    """
    Command to read and display the content of a file
    """
    
    name = "readFile"
    description = "Reads and displays the content of a file"
    category = "file"
    
    parameters = [
        {
            'name': 'file_path',
            'description': 'Path to the file to read',
            'required': True
        },
        {
            'name': 'max_lines',
            'description': 'Maximum number of lines to read (if not provided, reads the entire file)',
            'required': False,
            'default': None
        }
    ]
    
    examples = [
        {
            'command': 'qzx readFile myfile.txt',
            'description': 'Read the entire content of myfile.txt'
        },
        {
            'command': 'qzx readFile myfile.txt 10',
            'description': 'Read the first 10 lines of myfile.txt'
        },
        {
            'command': 'qzx readFile "path with spaces/myfile.txt"',
            'description': 'Read a file with spaces in the path'
        }
    ]
    
    def execute(self, file_path, max_lines=None):
        """
        Reads and displays the content of a file
        
        Args:
            file_path (str): Path to the file to read
            max_lines (int, optional): Maximum number of lines to read. If not provided, reads the entire file.
            
        Returns:
            Dictionary with file content and metadata
        """
        try:
            # Check if file exists
            if not os.path.exists(file_path):
                return f"Error: File '{file_path}' not found"
            
            if not os.path.isfile(file_path):
                return f"Error: '{file_path}' is not a file"
            
            # Get absolute path for display
            abs_path = os.path.abspath(file_path)
            
            # Get file stats
            file_stats = os.stat(file_path)
            file_size = file_stats.st_size
            modified_time = file_stats.st_mtime
            
            result = {
                "path": abs_path,
                "size": file_size,
                "size_readable": self._format_bytes(file_size),
                "modified": modified_time,
                "content": "",
                "read_complete": True
            }
            
            # Read file content
            with open(file_path, 'r', encoding='utf-8', errors='replace') as file:
                if max_lines is None:
                    # Read entire file
                    content = file.read()
                    result["content"] = content
                else:
                    # Try to convert max_lines to an integer
                    try:
                        max_lines = int(max_lines)
                    except ValueError:
                        return f"Error: max_lines must be an integer, got '{max_lines}'"
                    
                    # Read specified number of lines
                    lines = []
                    line_count = 0
                    
                    for i, line in enumerate(file):
                        if i >= max_lines:
                            result["read_complete"] = False
                            result["total_lines"] = "unknown"
                            break
                        lines.append(line)
                        line_count += 1
                    
                    result["lines_read"] = line_count
                    result["content"] = ''.join(lines)
                    
                    if not result["read_complete"]:
                        result["note"] = f"Only showing first {max_lines} lines"
            
            # Try to determine line count if we read the entire file
            if result["read_complete"]:
                result["total_lines"] = result["content"].count('\n') + (1 if result["content"] and not result["content"].endswith('\n') else 0)
            
            return result
        except Exception as e:
            return f"Error reading file: {str(e)}"
    
    def _format_bytes(self, bytes_value):
        """
        Format bytes to human-readable format
        
        Args:
            bytes_value (int): Bytes to format
            
        Returns:
            str: Formatted string with appropriate unit
        """
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_value < 1024 or unit == 'TB':
                return f"{bytes_value:.2f} {unit}"
            bytes_value /= 1024 