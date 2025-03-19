#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
WonderIfFileEmpty Command - Checks if a file is empty
"""

import os
from Core.command_base import CommandBase

class WonderIfFileEmptyCommand(CommandBase):
    """
    Command to check if a file is empty (has zero bytes)
    """
    
    name = "wonderIfFileEmpty"
    description = "Checks if a file is empty (has zero bytes)"
    category = "file"
    
    parameters = [
        {
            'name': 'file_path',
            'description': 'Path to the file to check',
            'required': True
        },
        {
            'name': 'consider_whitespace',
            'description': 'Whether to consider whitespace-only files as empty',
            'required': False,
            'default': False
        }
    ]
    
    examples = [
        {
            'command': 'qzx wonderIfFileEmpty /path/to/file.txt',
            'description': 'Check if file.txt is completely empty (zero bytes)'
        },
        {
            'command': 'qzx wonderIfFileEmpty /path/to/file.txt true',
            'description': 'Check if file.txt is empty or contains only whitespace'
        }
    ]
    
    def execute(self, file_path, consider_whitespace=False):
        """
        Checks if a file is empty
        
        Args:
            file_path (str): Path to the file to check
            consider_whitespace (bool, optional): Whether to consider whitespace-only files as empty
            
        Returns:
            Dictionary with the result of the check
        """
        try:
            # Validate file exists
            if not os.path.exists(file_path):
                return {
                    "success": False,
                    "error": f"File '{file_path}' does not exist"
                }
            
            # Validate it's a file
            if not os.path.isfile(file_path):
                return {
                    "success": False,
                    "error": f"'{file_path}' is not a file"
                }
            
            # Convert consider_whitespace to boolean if it's a string
            if isinstance(consider_whitespace, str):
                consider_whitespace = consider_whitespace.lower() in ('true', 'yes', 'y', '1')
            
            # Check if file is empty (has zero bytes)
            file_size = os.path.getsize(file_path)
            is_empty_by_size = file_size == 0
            
            # If we need to consider whitespace, and the file is not empty by size
            # we need to read it and check if it contains only whitespace
            is_whitespace_only = False
            if consider_whitespace and not is_empty_by_size:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        is_whitespace_only = content.strip() == ''
                except UnicodeDecodeError:
                    # If we can't decode as text, it's definitely not whitespace-only
                    is_whitespace_only = False
                except Exception:
                    # For any other read error, we'll assume it's not whitespace-only
                    is_whitespace_only = False
            
            # Determine final emptiness status
            is_empty = is_empty_by_size or (consider_whitespace and is_whitespace_only)
            
            # Prepare result
            result = {
                "success": True,
                "file_path": os.path.abspath(file_path),
                "is_empty": is_empty,
                "file_size": file_size,
                "file_size_readable": self._format_bytes(file_size),
                "consider_whitespace": consider_whitespace
            }
            
            # Add whitespace info if relevant
            if consider_whitespace and not is_empty_by_size:
                result["is_whitespace_only"] = is_whitespace_only
            
            # Add a message
            if is_empty_by_size:
                result["message"] = f"File '{file_path}' is completely empty (0 bytes)"
            elif is_whitespace_only and consider_whitespace:
                result["message"] = f"File '{file_path}' contains only whitespace ({file_size} bytes)"
            else:
                result["message"] = f"File '{file_path}' is not empty ({file_size} bytes)"
            
            return result
        
        except Exception as e:
            return {
                "success": False,
                "file_path": file_path,
                "error": str(e)
            }
    
    def _format_bytes(self, size):
        """
        Format bytes to human-readable size
        
        Args:
            size (int): Size in bytes
            
        Returns:
            str: Human-readable size string
        """
        for unit in ['B', 'KB', 'MB', 'GB', 'TB', 'PB']:
            if size < 1024.0 or unit == 'PB':
                break
            size /= 1024.0
        return f"{size:.2f} {unit}" 