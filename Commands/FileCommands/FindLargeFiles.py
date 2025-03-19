#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
FindLargeFiles Command - Searches for files matching a pattern with size filter
Using the centralized recursive file finder utility
"""

import os
import fnmatch
import re
import time
from datetime import datetime
from pathlib import Path
from Core.command_base import CommandBase
from Core.recursive_findfiles_utils import find_files, parse_recursive_parameter

class FindLargeFilesCommand(CommandBase):
    """
    Command to find files of specified type exceeding a minimum size
    
    Supports flags:
    -r, -R, --recursive: Enable unlimited recursive directory search
    -rN, --recursiveN: Enable recursive directory search up to N levels deep
    
    This version uses the centralized recursive file finder utility.
    """
    
    name = "findLargeFiles"
    description = "Searches for files with specific extensions that exceed a given size"
    category = "file"
    
    parameters = [
        {
            'name': 'directory',
            'description': 'Base directory to start the search from',
            'required': True
        },
        {
            'name': 'extension',
            'description': 'File extension to filter by (e.g., "*.pas", "*.txt")',
            'required': True
        },
        {
            'name': 'min_size',
            'description': 'Minimum file size in bytes',
            'required': True
        },
        {
            'name': 'recursive',
            'description': 'Recursion level: -r/--recursive for unlimited depth, -rN/--recursiveN for N levels deep',
            'required': False,
            'default': '-r'
        },
        {
            'name': 'sort_by',
            'description': 'Sort results by: "name", "size", "date"',
            'required': False,
            'default': 'size'
        }
    ]
    
    examples = [
        {
            'command': 'qzx findLargeFiles . *.pas 300',
            'description': 'Find all .pas files in current directory larger than 300 bytes'
        },
        {
            'command': 'qzx findLargeFiles src *.py 1024 -r',
            'description': 'Find all .py files in src directory and subdirectories larger than 1KB'
        },
        {
            'command': 'qzx findLargeFiles project *.js 5000 false name',
            'description': 'Find all .js files (non-recursive) larger than 5KB, sorted by name'
        }
    ]
    
    def _parse_size(self, size_str):
        """
        Parse a size string like '10MB' into bytes
        
        Args:
            size_str (str): Size string (e.g., '10MB', '1.5GB', '500KB')
            
        Returns:
            int: Size in bytes
            
        Raises:
            ValueError: If the format is invalid
        """
        if not size_str:
            return 0
            
        # If it's already a number, return it
        if isinstance(size_str, (int, float)):
            return int(size_str)
            
        # Parse string format
        size_str = str(size_str).strip().upper()
        
        # Handle different formats
        if size_str.endswith('B'):
            if size_str.endswith('KB'):
                multiplier = 1024
                size_value = float(size_str[:-2])
            elif size_str.endswith('MB'):
                multiplier = 1024 * 1024
                size_value = float(size_str[:-2])
            elif size_str.endswith('GB'):
                multiplier = 1024 * 1024 * 1024
                size_value = float(size_str[:-2])
            elif size_str.endswith('TB'):
                multiplier = 1024 * 1024 * 1024 * 1024
                size_value = float(size_str[:-2])
            else:  # Just bytes
                multiplier = 1
                size_value = float(size_str[:-1])
        else:
            # Try to parse as a plain number
            try:
                return int(size_str)
            except ValueError:
                raise ValueError(f"Invalid size format: {size_str}. Use formats like '10MB', '1.5GB', etc.")
                
        return int(size_value * multiplier)
    
    def _format_size(self, size_bytes):
        """
        Format a size in bytes to a human readable string
        
        Args:
            size_bytes (int): The size in bytes
            
        Returns:
            str: Human readable size string (e.g., '10.5 MB')
        """
        # Generate human-readable size
        units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
        size = float(size_bytes)
        unit_index = 0
        
        while size >= 1024.0 and unit_index < len(units) - 1:
            size /= 1024.0
            unit_index += 1
            
        # Format with appropriate precision
        if size < 10:
            return f"{size:.2f} {units[unit_index]}"
        elif size < 100:
            return f"{size:.1f} {units[unit_index]}"
        else:
            return f"{int(size)} {units[unit_index]}"
    
    def execute(self, directory, extension, min_size, recursive=None, sort_by='size'):
        """
        Searches for files matching a pattern that exceed a minimum size
        
        Args:
            directory (str): Directory to search in
            extension (str): File extension to filter by (e.g., 'jpg' or '.jpg')
            min_size (str): Minimum file size (e.g., '1MB', '500KB')
            recursive: Recursion level: none by default, -r/--recursive for unlimited, -rN/--recursiveN for N levels
            sort_by (str): Sort criteria ('size', 'name', or 'date')
            
        Returns:
            Dictionary with search results
        """
        try:
            # Process flags in command arguments if they exist
            import sys
            args = sys.argv
            recursive_flags = ['-r', '-R', '--recursive']
            recursive_found = any(flag in args for flag in recursive_flags)
            
            # Check that the directory exists
            if not os.path.exists(directory):
                return {
                    "success": False,
                    "error": f"Directory not found: {directory}"
                }
                
            if not os.path.isdir(directory):
                return {
                    "success": False,
                    "error": f"Not a directory: {directory}"
                }
            
            # Parse minimum size
            try:
                min_size_bytes = self._parse_size(min_size)
            except ValueError as e:
                return {
                    "success": False,
                    "error": f"Invalid minimum size format: {min_size}. {str(e)}"
                }
            
            # Parse recursive parameter - convert string flags or handle boolean
            if isinstance(recursive, str):
                recursive = parse_recursive_parameter(recursive)
            elif recursive_found:
                recursive = True
            
            # Validate sort_by
            valid_sort_options = ['name', 'size', 'date']
            if sort_by.lower() not in valid_sort_options:
                return {
                    "success": False,
                    "error": f"Invalid sort_by option: '{sort_by}'. Must be one of: {', '.join(valid_sort_options)}"
                }
            
            # Make sure extension has proper format (*.ext)
            if not extension.startswith('*'):
                extension = f'*{extension}' if extension.startswith('.') else f'*.{extension}'
            
            # Combine the directory and extension pattern
            search_pattern = os.path.join(directory, extension)
            
            # Find files using the centralized file finder
            matching_files = []
            
            def on_file_found(file_path):
                try:
                    file_size = os.path.getsize(file_path)
                    if file_size >= min_size_bytes:
                        matching_files.append({
                            "path": file_path,
                            "size": file_size,
                            "size_readable": self._format_size(file_size),
                            "modified": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(os.path.getmtime(file_path)))
                        })
                except (PermissionError, FileNotFoundError):
                    # Skip files we can't access
                    pass
            
            # Use find_files to search for files matching the pattern
            for _ in find_files(
                file_path_pattern=search_pattern,
                recursive=recursive,
                file_type='f',  # Only search for files
                on_file_found=on_file_found
            ):
                pass  # The callback already tracks the files
            
            # Get a descriptive recursion string for the result message
            recursion_message = ""
            if recursive is True or recursive is None:
                recursion_message = " (including all subdirectories)"
            elif isinstance(recursive, int) and recursive > 0:
                recursion_message = f" (including subdirectories up to {recursive} level{'s' if recursive > 1 else ''})"
            
            # Sort results
            if sort_by.lower() == 'name':
                matching_files.sort(key=lambda x: x["path"])
            elif sort_by.lower() == 'size':
                matching_files.sort(key=lambda x: x["size"], reverse=True)
            elif sort_by.lower() == 'date':
                matching_files.sort(key=lambda x: os.path.getmtime(x["path"]), reverse=True)
            
            # Calculate total size of all found files
            total_size = sum(f["size"] for f in matching_files)
            
            # Prepare result message
            if len(matching_files) == 0:
                message = f"No files found matching '{extension}' larger than {self._format_size(min_size_bytes)} in '{directory}'{recursion_message}"
            else:
                message = f"Found {len(matching_files)} files matching '{extension}' larger than {self._format_size(min_size_bytes)} in '{directory}'{recursion_message}"
                message += f", total size: {self._format_size(total_size)}"
            
            # Prepare result
            result = {
                "success": True,
                "message": message,
                "directory": os.path.abspath(directory),
                "extension": extension,
                "min_size": min_size,
                "min_size_bytes": min_size_bytes,
                "recursive": recursive,
                "sort_by": sort_by,
                "files_found": len(matching_files),
                "total_size": total_size,
                "total_size_readable": self._format_size(total_size),
                "files": matching_files
            }
            
            return result
        except Exception as e:
            return {
                "success": False,
                "directory": directory,
                "extension": extension,
                "min_size": min_size,
                "error": str(e)
            } 