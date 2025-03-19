#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ListFiles Command - Lists files in a directory with support for wildcards and recursive searching
Using the centralized recursive file finder utility
"""

import os
import time
import re
from pathlib import Path
from Core.command_base import CommandBase
from Core.recursive_findfiles_utils import find_files, parse_recursive_parameter

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
        """
        Lists files in a directory with support for wildcards and recursive searching
        
        Args:
            directory_path (str): Path to the directory to list files from
            pattern (str): File pattern to filter by (e.g., "*.txt", "doc*.pdf")
            recursive: Recursion level: none by default, -r/--recursive for unlimited, -rN/--recursiveN for N levels
            
        Returns:
            Dictionary with the list of files and metadata
        """
        try:
            # Process flags in command arguments if they exist
            import sys
            args = sys.argv
            recursive_flags = ['-r', '-R', '--recursive']
            recursive_found = any(flag in args for flag in recursive_flags)
            
            # Parse recursive parameter - convert string flags or handle boolean
            if isinstance(recursive, str):
                recursive = parse_recursive_parameter(recursive)
            elif recursive_found:
                recursive = True
            
            # Ensure directory exists
            if not os.path.exists(directory_path):
                return {
                    "success": False,
                    "message": f"Directory '{directory_path}' not found"
                }
            
            # If directory_path is a file (not a directory), list just that file if it matches the pattern
            if os.path.isfile(directory_path):
                # If file exists, add it to the result if it matches pattern
                filename = os.path.basename(directory_path)
                from fnmatch import fnmatch
                if fnmatch(filename, pattern):
                    file_stat = os.stat(directory_path)
                    return {
                        "success": True,
                        "directory": os.path.dirname(directory_path) or ".",
                        "pattern": pattern,
                        "recursive": recursive,
                        "files": [
                            {
                                "name": filename,
                                "path": directory_path,
                                "size": file_stat.st_size,
                                "size_formatted": self._format_size(file_stat.st_size),
                                "modified": file_stat.st_mtime,
                                "modified_formatted": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(file_stat.st_mtime)),
                                "is_directory": False
                            }
                        ],
                        "message": f"Found 1 file matching '{pattern}' in '{os.path.dirname(directory_path) or '.'}'"
                    }
                else:
                    return {
                        "success": True,
                        "directory": os.path.dirname(directory_path) or ".",
                        "pattern": pattern,
                        "recursive": recursive,
                        "files": [],
                        "message": f"No files found matching '{pattern}' in '{os.path.dirname(directory_path) or '.'}'"
                    }
            
            # Create the full path pattern for search
            if directory_path.endswith('/') or directory_path.endswith('\\'):
                # If the directory path ends with a separator, just append the pattern
                search_pattern = os.path.join(directory_path, pattern)
            else:
                # Otherwise, add a separator in between
                search_pattern = os.path.join(directory_path, pattern)
            
            # Use the centralized file finder to get all matching files and directories
            files_info = []
            
            def on_file_found(file_path):
                file_stat = os.stat(file_path)
                files_info.append({
                    "name": os.path.basename(file_path),
                    "path": file_path,
                    "size": file_stat.st_size,
                    "size_formatted": self._format_size(file_stat.st_size),
                    "modified": file_stat.st_mtime,
                    "modified_formatted": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(file_stat.st_mtime)),
                    "is_directory": False
                })
            
            def on_dir_found(dir_path):
                # Add directory with 0 size but show it as a directory
                dir_stat = os.stat(dir_path)
                files_info.append({
                    "name": os.path.basename(dir_path),
                    "path": dir_path,
                    "size": 0,  # Directories show as 0 size
                    "size_formatted": "-",
                    "modified": dir_stat.st_mtime,
                    "modified_formatted": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(dir_stat.st_mtime)),
                    "is_directory": True
                })
            
            # Find all files and directories using the centralized finder
            for _ in find_files(
                file_path_pattern=search_pattern,
                recursive=recursive,
                file_type=None,  # Get both files and directories
                on_file_found=on_file_found,
                on_dir_found=on_dir_found
            ):
                pass  # The callbacks track the files
            
            # Sort results by name
            files_info.sort(key=lambda x: x["name"].lower())
            
            # Create readable message about the results
            if len(files_info) == 0:
                message = f"No files found matching '{pattern}' in '{directory_path}'"
                if recursive:
                    message += " (including subdirectories)"
            else:
                # Count files and directories separately
                file_count = sum(1 for f in files_info if not f["is_directory"])
                dir_count = sum(1 for f in files_info if f["is_directory"])
                
                if file_count == 0 and dir_count > 0:
                    message = f"Found {dir_count} director{'ies' if dir_count != 1 else 'y'} matching '{pattern}' in '{directory_path}'"
                elif file_count > 0 and dir_count == 0:
                    message = f"Found {file_count} file{'s' if file_count != 1 else ''} matching '{pattern}' in '{directory_path}'"
                else:
                    message = f"Found {file_count} file{'s' if file_count != 1 else ''} and {dir_count} director{'ies' if dir_count != 1 else 'y'} matching '{pattern}' in '{directory_path}'"
                    
                if recursive:
                    message += " (including subdirectories)"
                    
            # Return the result
            return {
                "success": True,
                "directory": directory_path,
                "pattern": pattern,
                "recursive": recursive,
                "files": files_info,
                "message": message
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"Error listing files: {str(e)}"
            }
    
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