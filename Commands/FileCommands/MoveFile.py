#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MoveFile Command - Moves or renames a file or directory
Using the centralized recursive parameter utility
"""

import os
import shutil
from Core.command_base import CommandBase
from Core.recursive_findfiles_utils import parse_recursive_parameter

class MoveFileCommand(CommandBase):
    """
    Command to move or rename a file or directory
    
    Supports flags:
    -r, -R, --recursive: Enable unlimited recursive directory move
    -rN, --recursiveN: Enable recursive directory move up to N levels deep
    
    This version uses the centralized recursive parameter utility.
    """
    
    name = "moveFile"
    description = "Moves or renames a file or directory from source to destination"
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
            'description': 'For directories: -r/--recursive to move all contents, -rN/--recursiveN for N levels deep',
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
            'command': 'qzx moveFile source.txt destination.txt',
            'description': 'Move a file to another (or rename it)'
        },
        {
            'command': 'qzx moveFile myfile.txt archive/myfile.txt',
            'description': 'Move a file to a directory'
        },
        {
            'command': 'qzx moveFile sourcedir destinationdir -r',
            'description': 'Move a directory recursively (all contents)'
        },
        {
            'command': 'qzx moveFile sourcedir destinationdir -r2',
            'description': 'Move a directory recursively up to 2 levels deep'
        },
        {
            'command': 'qzx moveFile sourcedir destinationdir -r true',
            'description': 'Move a directory recursively and overwrite if exists'
        }
    ]
    
    def execute(self, source, destination, recursive=None, force=False):
        """
        Moves or renames a file or directory
        
        Args:
            source (str): Path to the source file or directory
            destination (str): Path to the destination file or directory
            recursive: Recursion level: none by default, -r/--recursive for unlimited, -rN/--recursiveN for N levels
            force (bool, optional): Whether to overwrite the destination if it exists
            
        Returns:
            Operation result
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
            
            # Determine the type of operation (file or directory)
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
            
            # Move based on type and recursion
            if source_is_dir:
                # If destination exists and force=True, remove it first
                if os.path.exists(destination) and force:
                    if os.path.isdir(destination):
                        shutil.rmtree(destination)
                    else:
                        os.remove(destination)
                
                if recursive is False or recursive == 0:
                    # Create only the directory without contents
                    os.makedirs(destination, exist_ok=True)
                    result["message"] = f"Directory '{source}' moved to '{destination}' (empty directory only)"
                elif recursive is True or recursive is None:
                    # Full recursive move - default shutil behavior
                    shutil.move(source, destination)
                    result["message"] = f"Directory '{source}' moved to '{destination}'{recursion_message}"
                else:
                    # Limited depth move
                    os.makedirs(destination, exist_ok=True)
                    
                    # Copy specific levels first, then remove source
                    def move_with_depth_limit(src, dst, current_depth=0):
                        """Recursively move with depth limit"""
                        if current_depth > recursive:
                            return
                        
                        # Process all items in the current directory
                        for item in os.listdir(src):
                            s = os.path.join(src, item)
                            d = os.path.join(dst, item)
                            
                            if os.path.isdir(s):
                                if current_depth < recursive:
                                    os.makedirs(d, exist_ok=True)
                                    move_with_depth_limit(s, d, current_depth + 1)
                            else:
                                shutil.copy2(s, d)
                                os.remove(s)
                        
                        # Try to remove the source directory if it's empty
                        try:
                            os.rmdir(src)
                        except OSError:
                            # Directory not empty, might contain files beyond our depth limit
                            pass
                    
                    # Start the limited recursive move
                    move_with_depth_limit(source, destination)
                    result["message"] = f"Directory '{source}' moved to '{destination}'{recursion_message}"
            else:
                # Move a single file
                shutil.move(source, destination)
                result["message"] = f"File '{source}' moved to '{destination}'"
            
            return result
        except Exception as e:
            return {
                "success": False,
                "source": source,
                "destination": destination,
                "error": str(e)
            } 