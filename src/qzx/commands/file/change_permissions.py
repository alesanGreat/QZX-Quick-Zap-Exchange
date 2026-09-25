#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ChangePermissions Command - Changes file or directory permissions
Using the centralized recursive file finder utility
"""

import os
import stat

from qzx.commands.file._permissions_workflow import change_permissions
from qzx.core.command_base import CommandBase
from qzx.core.recursive_findfiles_utils import find_files

class ChangePermissionsCommand(CommandBase):
    """
    Command to change file or directory permissions (similar to chmod)
    
    This version uses the centralized recursive file finder utility.
    """
    
    name = "changePermissions"
    description = "Changes permissions of a file or directory"
    category = "file"
    requires_explicit_approval = True
    backup_target_parameter = "path"
    
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
    
    def __init__(self, *, chmod=os.chmod, finder=find_files):
        """Expose mutation and traversal boundaries for safe deterministic tests."""
        self._chmod = chmod
        self._finder = finder

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
        """Change permissions through the semantic permissions workflow."""
        return change_permissions(self, path, mode, recursive)

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
