#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
CreateDirectory Command - Creates one or more directories at specified paths
"""

import os
from Core.command_base import CommandBase

class CreateDirectoryCommand(CommandBase):
    """
    Command to create one or more directories at specified paths
    """
    
    name = "createDirectory"
    description = "Creates one or more directories at specified paths"
    category = "file"
    
    parameters = [
        {
            'name': 'directory_paths',
            'description': 'One or more paths where directories should be created',
            'required': True
        }
    ]
    
    examples = [
        {
            'command': 'qzx createDirectory "ProjectFolder"',
            'description': 'Create a single directory named "ProjectFolder"'
        },
        {
            'command': 'qzx createDirectory "src/components" "src/styles" "src/utils"',
            'description': 'Create multiple directories for a project structure'
        }
    ]
    
    def execute(self, *directory_paths):
        """
        Creates one or more directories at the specified paths
        
        Args:
            *directory_paths: One or more paths where directories should be created
            
        Returns:
            String with results of directory creation attempts
        """
        if not directory_paths:
            return "Error: No directory paths provided"
        
        results = []
        success_count = 0
        
        for path in directory_paths:
            try:
                os.makedirs(path, exist_ok=True)
                results.append(f"✓ Directory created: {path}")
                success_count += 1
            except Exception as e:
                results.append(f"✗ Error creating directory '{path}': {str(e)}")
        
        summary = f"Created {success_count} of {len(directory_paths)} directories"
        return f"{summary}\n" + "\n".join(results) 