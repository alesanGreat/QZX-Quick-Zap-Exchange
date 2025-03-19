#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ChangePermissions Command - Changes file or directory permissions
Using the centralized recursive file finder utility
"""

import os
import platform
import stat
from Core.command_base import CommandBase
from Core.recursive_findfiles_utils import find_files, parse_recursive_parameter

class ChangePermissionsCommand(CommandBase):
    """
    Command to change file or directory permissions (similar to chmod)
    
    This version uses the centralized recursive file finder utility.
    """
    
    name = "changePermissions"
    description = "Changes permissions of a file or directory"
    category = "file"
    
    parameters = [
        {
            'name': 'path',
            'description': 'Path to the file or directory',
            'required': True
        },
        {
            'name': 'mode',
            'description': 'Permission mode in octal (e.g., 755) or string format (e.g., "a+x")',
            'required': True
        },
        {
            'name': 'recursive',
            'description': 'Whether to apply permissions recursively: -r/--recursive for unlimited, -rN/--recursiveN for N levels',
            'required': False,
            'default': False
        }
    ]
    
    examples = [
        {
            'command': 'qzx changePermissions myfile.txt 644',
            'description': 'Change file permissions to 644 (rw-r--r--)'
        },
        {
            'command': 'qzx changePermissions myscript.sh "a+x"',
            'description': 'Make a script executable for all users'
        },
        {
            'command': 'qzx changePermissions mydir 755 -r',
            'description': 'Change directory permissions recursively'
        },
        {
            'command': 'qzx changePermissions mydir 755 -r2',
            'description': 'Change directory permissions up to 2 levels deep'
        }
    ]
    
    def execute(self, path, mode, recursive=False):
        """
        Changes permissions of a file or directory
        
        Args:
            path (str): Path to the file or directory
            mode (str/int): Permission mode in octal (e.g., 755) or string format (e.g., "a+x")
            recursive: Recursion level: none by default, -r/--recursive for unlimited, -rN/--recursiveN for N levels
            
        Returns:
            Operation result
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
            
            # Check if path exists
            if not os.path.exists(path):
                return {
                    "success": False,
                    "error": f"Path '{path}' does not exist"
                }
            
            # Convert mode to integer if given as octal string
            if isinstance(mode, str):
                if mode.isdigit():
                    # Convert from octal string (e.g., "755") to integer
                    mode = int(mode, 8)
                else:
                    # Handle symbolic mode (e.g., "u+x")
                    # This would require complex parsing or using a library like 'chmod'
                    return {
                        "success": False,
                        "error": f"Symbolic mode '{mode}' is not supported yet. Use numeric octal mode (e.g., 755)."
                    }
            
            # Prepare the result
            result = {
                "path": os.path.abspath(path),
                "type": "directory" if os.path.isdir(path) else "file",
                "mode": oct(mode)[2:],  # Convert integer to octal string without '0o' prefix
                "recursive": recursive,
                "success": True
            }
            
            # Apply permissions to a single file
            if os.path.isfile(path):
                os.chmod(path, mode)
                result["message"] = f"Changed permissions of '{path}' to {result['mode']}"
                return result
                
            # Apply permissions to a directory
            elif os.path.isdir(path):
                # For non-recursive operation, just change the directory itself
                if recursive is False or recursive == 0:
                    os.chmod(path, mode)
                    result["message"] = f"Changed permissions of '{path}' to {result['mode']}"
                    return result
                    
                # For recursive operation, use the find_files utility
                count = 0
                
                # Apply permissions to the main directory
                os.chmod(path, mode)
                count += 1
                
                # Define callbacks for files and directories
                def file_callback(file_path):
                    nonlocal count
                    try:
                        os.chmod(file_path, mode)
                        count += 1
                        return True
                    except Exception as e:
                        # Add warning but continue
                        if "warnings" not in result:
                            result["warnings"] = []
                        result["warnings"].append(f"Failed to change permissions for '{file_path}': {str(e)}")
                        return True
                
                def dir_callback(dir_path):
                    nonlocal count
                    try:
                        os.chmod(dir_path, mode)
                        count += 1
                        return True
                    except Exception as e:
                        # Add warning but continue
                        if "warnings" not in result:
                            result["warnings"] = []
                        result["warnings"].append(f"Failed to change permissions for '{dir_path}': {str(e)}")
                        return True
                
                # Find and process all files and directories
                find_files(
                    path,
                    recursive=recursive,
                    file_callback=file_callback,
                    dir_callback=dir_callback,
                    include_dirs=True
                )
                
                result["message"] = f"Changed permissions of '{path}' and its contents to {result['mode']} (recursive)"
                result["items_modified"] = count
                
            return result
        except Exception as e:
            return {
                "success": False,
                "path": path,
                "error": str(e)
            }
            
    def _format_permissions(self, mode):
        """
        Formats numeric permission mode to human-readable format (e.g., 'rw-r--r--')
        
        Args:
            mode (int): The numeric permission mode
            
        Returns:
            str: Human-readable permission string
        """
        perm_string = ""
        
        # User permissions
        perm_string += 'r' if mode & stat.S_IRUSR else '-'
        perm_string += 'w' if mode & stat.S_IWUSR else '-'
        perm_string += 'x' if mode & stat.S_IXUSR else '-'
        
        # Group permissions
        perm_string += 'r' if mode & stat.S_IRGRP else '-'
        perm_string += 'w' if mode & stat.S_IWGRP else '-'
        perm_string += 'x' if mode & stat.S_IXGRP else '-'
        
        # Other permissions
        perm_string += 'r' if mode & stat.S_IROTH else '-'
        perm_string += 'w' if mode & stat.S_IWOTH else '-'
        perm_string += 'x' if mode & stat.S_IXOTH else '-'
        
        return perm_string
        
    def _get_symbolic_mode(self, mode):
        """
        Converts numeric mode to symbolic notation (e.g., 'a+x')
        Not fully implemented - would need more complex parsing
        
        Args:
            mode (int): The numeric permission mode
            
        Returns:
            str: Symbolic permission string
        """
        # This would require more complex implementation
        return f"0{oct(mode)[2:]}" 