#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
FindBrokenSymlinks Command - Scans directories recursively for symbolic links pointing to deleted/missing targets.
"""

from qzx.commands.file._broken_symlink_scan import execute_broken_symlink_scan
from qzx.core.command_base import CommandBase

class FindBrokenSymlinksCommand(CommandBase):
    """
    Command to identify symbolic links and junctions pointing to nonexistent targets.
    """
    
    name = "findBrokenSymlinks"
    description = "Scans directories for broken symbolic links (pointing to nonexistent files or folders)"
    category = "file"
    
    parameters = [
        {
            'name': 'folder_path',
            'description': 'Directory to scan (defaults to current directory)',
            'required': False,
            'default': '.'
        },
        {
            'name': 'max_depth',
            'description': 'Maximum depth level to walk directories recursively (defaults to 4)',
            'required': False,
            'default': '4'
        }
    ]
    
    examples = [
        {
            'command': 'qzx findBrokenSymlinks',
            'description': 'Search for broken symlinks in the current directory'
        },
        {
            'command': 'qzx findBrokenSymlinks C:/some/path',
            'description': 'Search for broken symlinks in C:/some/path'
        }
    ]
    
    def execute(self, folder_path='.', max_depth='4'):
        """Scan for broken symbolic links within the requested depth."""
        return execute_broken_symlink_scan(folder_path, max_depth)
