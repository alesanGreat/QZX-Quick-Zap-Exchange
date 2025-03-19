#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
CountLinesInFile Command - Counts the number of lines in files with support for wildcards and recursive searching
Using the centralized recursive file finder utility
"""

import os
import re
from collections import defaultdict
from Core.command_base import CommandBase
from Core.recursive_findfiles_utils import find_files, parse_recursive_parameter

class CountLinesInFileCommand(CommandBase):
    """
    Command to count the number of lines in files with support for wildcards and recursive searching
    
    Supports flags:
    -r, -R, --recursive: Enable unlimited recursive directory search
    -rN, --recursiveN: Enable recursive directory search up to N levels deep
    
    This version uses the centralized recursive file finder utility.
    """
    
    name = "countLinesInFile"
    description = "Counts the number of lines in files with support for wildcards and recursive searching"
    category = "file"
    
    parameters = [
        {
            'name': 'file_path',
            'description': 'Path to the file(s) to count lines in. Supports wildcards like "*.py"',
            'required': True
        },
        {
            'name': 'recursive',
            'description': 'Recursion level: -r/--recursive for unlimited depth, -rN/--recursiveN for N levels deep',
            'required': False,
            'default': None
        },
        {
            'name': 'ignore_empty',
            'description': 'Whether to ignore empty lines when counting',
            'required': False,
            'default': False
        }
    ]
    
    examples = [
        {
            'command': 'qzx countLinesInFile "script.py"',
            'description': 'Count the number of lines in a Python script'
        },
        {
            'command': 'qzx countLinesInFile "data/logs.txt"',
            'description': 'Count the number of lines in a log file'
        },
        {
            'command': 'qzx countLinesInFile "*.py"',
            'description': 'Count the number of lines in all Python files in the current directory'
        },
        {
            'command': 'qzx countLinesInFile "src/**/*.js" -r',
            'description': 'Count the number of lines in all JavaScript files in the src directory and its subdirectories'
        },
        {
            'command': 'qzx countLinesInFile "*.txt" -r2 true',
            'description': 'Count the number of non-empty lines in all text files in the current directory and subdirectories up to 2 levels deep'
        }
    ]
    
    def _count_lines(self, file_path, ignore_empty=False):
        """
        Count lines in a single file
        
        Args:
            file_path (str): Path to the file
            ignore_empty (bool): Whether to ignore empty lines
            
        Returns:
            tuple: (line_count, non_empty_lines, success, error_message)
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as file:
                if ignore_empty:
                    lines = [line for line in file if line.strip()]
                    return (len(lines), len(lines), True, None)
                else:
                    lines = file.readlines()
                    non_empty = sum(1 for line in lines if line.strip())
                    return (len(lines), non_empty, True, None)
        except Exception as e:
            return (0, 0, False, str(e))
    
    def execute(self, file_path, recursive=None, ignore_empty=False):
        """
        Counts the number of lines in files with support for wildcards and recursive searching
        
        Args:
            file_path: Path to the file(s) to count lines in. Supports wildcards like "*.py"
            recursive: Recursion level: none by default, -r/--recursive for unlimited, -rN/--recursiveN for N levels
            ignore_empty: Whether to ignore empty lines when counting
            
        Returns:
            Dictionary with line count results or error message
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
            
            # Convert ignore_empty parameter if it's a string
            if isinstance(ignore_empty, str):
                ignore_empty = ignore_empty.lower() in ('true', 'yes', 'y', '1')
            
            # Find matching files using centralized file finder
            matching_files = []
            
            def on_file_found(found_file):
                matching_files.append(found_file)
                
            # Use the centralized file finder to get all matching files
            for _ in find_files(
                file_path_pattern=file_path,
                recursive=recursive,
                file_type='f',  # Only search for files, not directories
                on_file_found=on_file_found
            ):
                pass  # The callback already tracks the files
            
            # Get a descriptive recursion string for the result message
            recursion_message = ""
            if recursive is True or recursive is None:
                recursion_message = " (including all subdirectories)"
            elif isinstance(recursive, int) and recursive > 0:
                recursion_message = f" (including subdirectories up to {recursive} level{'s' if recursive > 1 else ''})"
            
            if not matching_files:
                return {
                    "success": True,
                    "files_found": 0,
                    "message": f"No files found matching '{file_path}'{recursion_message}"
                }
            
            # Count lines in each file
            results = {}
            total_lines = 0
            total_non_empty = 0
            total_success = 0
            errors = []
            
            for file in matching_files:
                lines, non_empty, success, error = self._count_lines(file, ignore_empty)
                if success:
                    results[file] = {
                        "lines": lines if not ignore_empty else "N/A",
                        "non_empty_lines": non_empty,
                        "counted": lines if ignore_empty else non_empty
                    }
                    total_lines += lines
                    total_non_empty += non_empty
                    total_success += 1
                else:
                    results[file] = {
                        "error": error
                    }
                    errors.append(f"{file}: {error}")
            
            # Prepare result summary
            line_type = "non-empty lines" if ignore_empty else "lines"
            if len(matching_files) == 1:
                # Result for single file
                file_path = matching_files[0]
                if file_path in results and "error" not in results[file_path]:
                    count = results[file_path]["counted"]
                    message = f"File '{file_path}' contains {count} {line_type}"
                    if not ignore_empty and results[file_path]["non_empty_lines"] != results[file_path]["lines"]:
                        empty_lines = results[file_path]["lines"] - results[file_path]["non_empty_lines"]
                        message += f" ({empty_lines} empty line{'s' if empty_lines != 1 else ''})"
                else:
                    message = f"Error processing file '{file_path}': {results[file_path]['error']}"
            else:
                # Result for multiple files
                total_counted = total_non_empty if ignore_empty else total_lines
                message = f"Found {len(matching_files)} files matching '{file_path}'{recursion_message}\n"
                message += f"Total {line_type}: {total_counted}"
                
                if total_success < len(matching_files):
                    message += f"\nSuccessfully processed {total_success} of {len(matching_files)} files"
                    message += f"\nErrors: {len(errors)}"
            
            # Return the result
            return {
                "success": True,
                "files_found": len(matching_files),
                "files_processed": total_success,
                "total_lines": total_lines if not ignore_empty else "N/A",
                "total_non_empty_lines": total_non_empty,
                "total_counted": total_non_empty if ignore_empty else total_lines,
                "errors": errors,
                "file_results": results,
                "message": message
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Error: {str(e)}"
            } 