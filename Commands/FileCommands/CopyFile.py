#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
CopyFile Command - Copies a file or directory
Using the centralized recursive file finder utility
"""

import os
import shutil
from Core.command_base import CommandBase
from Core.recursive_findfiles_utils import parse_recursive_parameter

class CopyFileCommand(CommandBase):
    """
    Command to copy a file or directory
    
    Supports flags:
    -r, -R, --recursive: Enable unlimited recursive directory copy
    -rN, --recursiveN: Enable recursive directory copy up to N levels deep
    
    This version uses the centralized recursive parameter utility.
    """
    
    name = "copyFile"
    description = "Copies a file or directory from source to destination"
    category = "file"
    
    parameters = [
        {
            'name': 'source',
            'description': 'Path to the source file or directory',
            'required': True
        },
        {
            'name': 'destination',
            'description': 'Path to the destination file or directory',
            'required': True
        },
        {
            'name': 'recursive',
            'description': 'For directories: -r/--recursive to copy all contents, -rN/--recursiveN for N levels deep',
            'required': False,
            'default': None
        },
        {
            'name': 'force',
            'description': 'Whether to overwrite the destination if it exists',
            'required': False,
            'default': False
        }
    ]
    
    examples = [
        {
            'command': 'qzx copyFile source.txt destination.txt',
            'description': 'Copy a file to another file'
        },
        {
            'command': 'qzx copyFile myfile.txt backup/myfile.txt',
            'description': 'Copy a file to a directory'
        },
        {
            'command': 'qzx copyFile sourcedir destinationdir -r',
            'description': 'Copy a directory recursively (all contents)'
        },
        {
            'command': 'qzx copyFile sourcedir destinationdir -r2',
            'description': 'Copy a directory recursively up to 2 levels deep'
        },
        {
            'command': 'qzx copyFile sourcedir destinationdir -r true',
            'description': 'Copy a directory recursively and overwrite if exists'
        }
    ]
    
    def execute(self, source, destination, recursive=None, force=False):
        """
        Copies a file or directory
        
        Args:
            source (str): Path to the source file or directory
            destination (str): Path to the destination file or directory
            recursive: Recursion level: none by default, -r/--recursive for unlimited, -rN/--recursiveN for N levels
            force (bool, optional): Whether to overwrite the destination if it exists
            
        Returns:
            Success message or error
        """
        try:
            # Process flags in command arguments if they exist
            import sys
            args = sys.argv
            recursive_flags = ['-r', '-R', '--recursive']
            recursive_found = any(flag in args for flag in recursive_flags)
            
            # Convert force to boolean if it's a string
            if isinstance(force, str):
                force = force.lower() in ('true', 'yes', 'y', '1')
            
            # Parse recursive parameter
            if isinstance(recursive, str):
                recursive = parse_recursive_parameter(recursive)
            elif recursive_found:
                recursive = True
            
            # Check if source exists
            if not os.path.exists(source):
                return {
                    "success": False,
                    "error": f"Source '{source}' does not exist"
                }
            
            # Check if destination exists and if we should overwrite
            if os.path.exists(destination) and not force:
                return {
                    "success": False,
                    "error": f"Destination '{destination}' already exists. Use force=True to overwrite."
                }
            
            # Create destination directory if it doesn't exist
            dest_dir = os.path.dirname(destination)
            if dest_dir and not os.path.exists(dest_dir):
                os.makedirs(dest_dir)
            
            # Determine the type of copy (file or directory)
            source_is_dir = os.path.isdir(source)
            
            # Prepare the result
            result = {
                "source": os.path.abspath(source),
                "destination": os.path.abspath(destination),
                "type": "directory" if source_is_dir else "file",
                "recursive": recursive,
                "force": force,
                "success": True
            }
            
            # Get a descriptive recursion string for the result message
            recursion_message = ""
            if recursive is True or recursive is None:
                recursion_message = " (all contents)"
            elif isinstance(recursive, int) and recursive > 0:
                recursion_message = f" (up to {recursive} level{'s' if recursive > 1 else ''})"
            
            if source_is_dir:
                # Directory copy with recursion handling
                if os.path.exists(destination) and force:
                    # If destination exists and force=True, remove it first
                    shutil.rmtree(destination, ignore_errors=True)
                
                if recursive is False or recursive == 0:
                    # Create only the directory without contents
                    os.makedirs(destination, exist_ok=True)
                    result["message"] = f"Directory '{source}' copied to '{destination}' (empty directory only)"
                elif recursive is True or recursive is None:
                    # Full recursive copy
                    shutil.copytree(source, destination)
                    result["message"] = f"Directory '{source}' copied to '{destination}'{recursion_message}"
                else:
                    # Limited recursive copy (up to N levels)
                    os.makedirs(destination, exist_ok=True)
                    
                    def copy_with_depth_limit(src, dst, current_depth=0):
                        """Recursively copy with depth limit"""
                        if current_depth > recursive:
                            return
                        
                        # Copy all items in the current directory
                        for item in os.listdir(src):
                            s = os.path.join(src, item)
                            d = os.path.join(dst, item)
                            
                            if os.path.isdir(s):
                                if current_depth < recursive:
                                    os.makedirs(d, exist_ok=True)
                                    copy_with_depth_limit(s, d, current_depth + 1)
                            else:
                                shutil.copy2(s, d)
                    
                    # Start the limited recursive copy
                    copy_with_depth_limit(source, destination)
                    result["message"] = f"Directory '{source}' copied to '{destination}'{recursion_message}"
            else:
                # Copy a single file
                shutil.copy2(source, destination)
                
                # Get file information
                src_size = os.path.getsize(source)
                dst_size = os.path.getsize(destination)
                
                result["message"] = f"File '{source}' copied to '{destination}'"
                result["file_size"] = src_size
                result["file_size_readable"] = self._format_bytes(src_size)
                
                # Verify that the size matches
                if src_size != dst_size:
                    result["warning"] = f"Source file size ({src_size} bytes) and destination file size ({dst_size} bytes) do not match"
            
            return result
        except Exception as e:
            return {
                "success": False,
                "source": source,
                "destination": destination,
                "error": str(e)
            }
    
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