#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
CreateDirectory Command - Creates one or more directories at specified paths
"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from qzx.core.command_base import CommandBase

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
            'required': True,
            'type': 'str',
            'is_variadic': True
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
            Structured operation result
        """
        if not directory_paths:
            return {
                "success": False,
                "error_code": "missing_argument",
                "error": "No directory paths were provided.",
                "message": "Provide at least one directory path to create."
            }
        
        results = []
        success_count = 0
        
        for path in directory_paths:
            try:
                os.makedirs(path, exist_ok=True)
                results.append(f"✓ Directory created: {path}")
                success_count += 1
            except Exception as e:
                results.append(f"✗ Error creating directory '{path}': {str(e)}")
        
        failed_count = len(directory_paths) - success_count
        summary = f"Created {success_count} of {len(directory_paths)} directories."
        return {
            "success": failed_count == 0,
            "message": summary,
            "details": {
                "requested": len(directory_paths),
                "created": success_count,
                "failed": failed_count,
                "results": results
            }
        }
