#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ReadFile Command - Reads and displays the content of a file
"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from qzx.core.command_base import CommandBase

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
                return {
                    "success": False,
                    "error_code": "file_not_found",
                    "error": f"File '{file_path}' was not found.",
                    "message": "Check the path and try again.",
                    "details": {"path": os.path.abspath(file_path)},
                }
            
            if not os.path.isfile(file_path):
                return {
                    "success": False,
                    "error_code": "not_a_file",
                    "error": f"'{file_path}' is not a regular file.",
                    "message": "readFile accepts files, not directories.",
                    "details": {"path": os.path.abspath(file_path)},
                }
            
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
                    except (TypeError, ValueError):
                        return {
                            "success": False,
                            "error_code": "invalid_max_lines",
                            "error": f"max_lines must be an integer, got '{max_lines}'.",
                            "message": "Provide a non-negative integer line limit.",
                        }
                    if max_lines < 0:
                        return {
                            "success": False,
                            "error_code": "invalid_max_lines",
                            "error": "max_lines cannot be negative.",
                            "message": "Provide a non-negative integer line limit.",
                        }
                    
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
            
            return {
                "success": True,
                "message": (
                    f"Read {result.get('lines_read', result.get('total_lines', 0))} "
                    f"line(s) from '{abs_path}'."
                ),
                "content": result["content"],
                "details": result,
            }
        except Exception as e:
            return {
                "success": False,
                "error_code": "read_failed",
                "error": str(e),
                "message": f"Could not read '{file_path}'.",
            }
    
