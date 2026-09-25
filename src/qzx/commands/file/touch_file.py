#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
TouchFile Command - Creates an empty file or updates the timestamp of an existing file
"""

from qzx.commands.file._touch_file_operation import execute_touch_file
from qzx.core.command_base import CommandBase

class TouchFileCommand(CommandBase):
    """
    Command to create an empty file or update the timestamp of an existing file
    """
    
    name = "touchFile"
    description = "Creates an empty file or updates the timestamp of an existing file"
    category = "file"
    
    parameters = [
        {
            'name': 'path',
            'description': 'Path to the file to create or update',
            'required': True
        },
        {
            'name': 'create_dirs',
            'description': 'Whether to create parent directories if they do not exist',
            'required': False,
            'default': False
        },
        {
            'name': 'content',
            'description': 'Content to write to the file',
            'required': False,
            'default': ''
        }
    ]
    
    examples = [
        {
            'command': 'qzx touchFile newfile.txt',
            'description': 'Create an empty file or update its timestamp'
        },
        {
            'command': 'qzx touchFile dir/newfile.txt true',
            'description': 'Create a file and its parent directories if they do not exist'
        },
        {
            'command': 'qzx touchFile file.txt false "Hello World"',
            'description': 'Create a file with content or update an existing file'
        }
    ]
    
    def execute(self, path, create_dirs=False, content=''):
        """Create a file or update its timestamp/content."""
        return execute_touch_file(path, create_dirs, content)
