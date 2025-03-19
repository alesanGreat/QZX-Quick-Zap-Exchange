#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
DeleteFile Command - Deletes a file or directory
Using the centralized recursive parameter utility
"""

import os
import shutil
import re
from Core.command_base import CommandBase
from Core.recursive_findfiles_utils import parse_recursive_parameter

class DeleteFileCommand(CommandBase):
    """
    Command to delete a file or directory
    
    Supports flags:
    -r, -R, --recursive: Enable unlimited recursive directory deletion
    -rN, --recursiveN: Enable recursive directory deletion up to N levels deep
    
    This version uses the centralized recursive parameter utility.
    """
    
    name = "deleteFile"
    description = "Deletes a file or directory from the filesystem"
    category = "file"
    
    parameters = [
        {
            'name': 'target',
            'description': 'Path to the file or directory to delete',
            'required': True
        },
        {
            'name': 'recursive',
            'description': 'For directories: -r/--recursive for removal, -rN/--recursiveN for N levels deep',
            'required': False,
            'default': None
        },
        {
            'name': 'force',
            'description': 'Whether to ignore errors',
            'required': False,
            'default': False
        }
    ]
    
    examples = [
        {
            'command': 'qzx deleteFile myfile.txt',
            'description': 'Delete a file'
        },
        {
            'command': 'qzx deleteFile mydir -r',
            'description': 'Delete a directory and its contents recursively'
        },
        {
            'command': 'qzx deleteFile mydir -r2',
            'description': 'Delete a directory and contents up to 2 levels deep'
        },
        {
            'command': 'qzx deleteFile mydir false true',
            'description': 'Try to delete an empty directory, ignoring errors'
        }
    ]
    
    def execute(self, target, recursive=None, force=False):
        """
        Deletes a file or directory
        
        Args:
            target (str): Path to the file or directory to delete
            recursive: Recursion level: none by default, -r/--recursive for unlimited, -rN/--recursiveN for N levels
            force (bool, optional): Whether to ignore errors
            
        Returns:
            Operation result
        """
        try:
            # Process flags in command arguments if they exist
            import sys
            args = sys.argv
            recursive_flags = ['-r', '-R', '--recursive']
            recursive_found = any(flag in args for flag in recursive_flags)
            
            # Convert force parameter to boolean if it's a string
            if isinstance(force, str):
                force = force.lower() in ('true', 'yes', 'y', '1')
            
            # Parse recursive parameter - convert string flags or handle boolean
            if isinstance(recursive, str):
                recursive = parse_recursive_parameter(recursive)
            elif recursive_found:
                recursive = True
            
            # Check if target exists
            if not os.path.exists(target):
                if force:
                    return {
                        "success": True,
                        "warning": f"Target '{target}' does not exist, but force=True so continuing"
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Target '{target}' does not exist"
                    }
            
            # Get a descriptive recursion string for the result message
            recursion_message = ""
            if recursive is True or recursive is None:
                recursion_message = " (including all contents)"
            elif isinstance(recursive, int) and recursive > 0:
                recursion_message = f" (including contents up to {recursive} level{'s' if recursive > 1 else ''})"
            
            # Prepare the result
            result = {
                "target": os.path.abspath(target),
                "type": "directory" if os.path.isdir(target) else "file",
                "recursive": recursive,
                "force": force,
                "success": True
            }
            
            # Handle deletion based on target type and recursion depth
            if os.path.isfile(target):
                # For files, just delete
                os.remove(target)
                result["message"] = f"File '{target}' has been deleted"
            elif os.path.isdir(target):
                if recursive == 0 or recursive is False:
                    # Try to delete empty directory
                    try:
                        os.rmdir(target)
                        result["message"] = f"Empty directory '{target}' has been deleted"
                    except OSError as e:
                        if force:
                            result["warning"] = f"Could not delete directory '{target}', but force=True so continuing: {str(e)}"
                        else:
                            return {
                                "success": False,
                                "error": f"Could not delete directory '{target}'. Is it empty? Error: {str(e)}"
                            }
                elif recursive is True or recursive is None:
                    # Full recursive delete
                    try:
                        shutil.rmtree(target)
                        result["message"] = f"Directory '{target}' and all its contents have been deleted"
                    except OSError as e:
                        if force:
                            result["warning"] = f"Error during recursive deletion of '{target}', but force=True so continuing: {str(e)}"
                        else:
                            return {
                                "success": False,
                                "error": f"Error during recursive deletion of '{target}': {str(e)}"
                            }
                else:
                    # Limited depth delete
                    errors = []
                    for root, dirs, files in os.walk(target, topdown=False):
                        # Calculate current depth relative to target
                        rel_path = os.path.relpath(root, target)
                        current_depth = 0 if rel_path == '.' else rel_path.count(os.sep) + 1
                        
                        # Skip if depth exceeds the limit
                        if current_depth > recursive:
                            continue
                        
                        # Delete files at this level
                        for file in files:
                            try:
                                os.remove(os.path.join(root, file))
                            except OSError as e:
                                errors.append(f"Error deleting file '{os.path.join(root, file)}': {str(e)}")
                        
                        # Try to delete this directory if it's empty
                        try:
                            os.rmdir(root)
                        except OSError as e:
                            errors.append(f"Error deleting directory '{root}': {str(e)}")
                    
                    # Handle errors
                    if errors:
                        if force:
                            result["warning"] = f"Some errors occurred during deletion with depth={recursive}, but force=True so continuing"
                            result["errors"] = errors
                        else:
                            return {
                                "success": False,
                                "error": f"Errors occurred during deletion with depth={recursive}",
                                "errors": errors
                            }
                    else:
                        result["message"] = f"Directory '{target}' and contents up to depth {recursive} have been deleted"
            
            return result
        except Exception as e:
            if force:
                return {
                    "success": True,
                    "warning": f"Error during deletion of '{target}', but force=True so continuing: {str(e)}"
                }
            return {
                "success": False,
                "error": str(e)
            }
    
    def _format_bytes(self, bytes_value):
        """
        Formatea bytes a un formato legible
        
        Args:
            bytes_value (int): Bytes para formatear
            
        Returns:
            str: Cadena formateada con la unidad apropiada
        """
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_value < 1024 or unit == 'TB':
                return f"{bytes_value:.2f} {unit}"
            bytes_value /= 1024 