#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Example of using the recursive_findfiles_utils module in a command
"""

import os
import time
from typing import List, Dict, Any, Optional
from Core.command_base import CommandBase
from Core.recursive_findfiles_utils import find_files, parse_recursive_parameter

class ExampleFindCommand(CommandBase):
    """
    Example command showing how to use the centralized recursive file finding module
    """
    
    name = "exampleFind"
    description = "Example showing how to use the recursive file finding utility"
    category = "file"
    
    parameters = [
        {
            'name': 'directory',
            'description': 'Directory to search in',
            'required': False,
            'default': '.'
        },
        {
            'name': 'pattern',
            'description': 'File pattern to search for (e.g., "*.txt")',
            'required': False,
            'default': '*'
        },
        {
            'name': 'recursive',
            'description': 'Recursion level: -r/--recursive for unlimited depth, -rN/--recursiveN for N levels deep',
            'required': False,
            'default': None
        },
        {
            'name': 'exclude',
            'description': 'File patterns to exclude (comma-separated)',
            'required': False,
            'default': None
        },
        {
            'name': 'exclude_dir',
            'description': 'Directory patterns to exclude (comma-separated)',
            'required': False,
            'default': None
        }
    ]
    
    examples = [
        {
            'command': 'qzx exampleFind . *.py',
            'description': 'Find all Python files in current directory'
        },
        {
            'command': 'qzx exampleFind src *.js -r',
            'description': 'Find all JavaScript files in src directory and subdirectories'
        },
        {
            'command': 'qzx exampleFind . *.txt -r2',
            'description': 'Find text files up to 2 levels deep'
        },
        {
            'command': 'qzx exampleFind . * -r --exclude="*.tmp,*.log"',
            'description': 'Find all files recursively, excluding temp and log files'
        }
    ]
    
    def execute(self, directory='.', pattern='*', recursive=None, exclude=None, exclude_dir=None):
        """
        Execute the example command
        
        Args:
            directory (str): Directory to search in
            pattern (str): File pattern to search for
            recursive: Recursion parameter
            exclude (str): Comma-separated list of patterns to exclude
            exclude_dir (str): Comma-separated list of directory patterns to exclude
        """
        # Process exclude patterns
        exclude_patterns = exclude.split(',') if exclude else []
        exclude_directories = exclude_dir.split(',') if exclude_dir else []
        
        # Build the full pattern
        file_path_pattern = os.path.join(directory, pattern)
        
        # Create a callback for real-time feedback
        found_count = 0
        start_time = time.time()
        
        def on_file_found(file_path):
            nonlocal found_count
            found_count += 1
            # Print each file as it's found (real-time feedback)
            print(f"Found: {file_path}")
        
        # Run the search with real-time feedback using the centralized utility
        print(f"Searching for files matching '{pattern}' in '{directory}'...")
        
        # Use the generator version for real-time processing
        for _ in find_files(
            file_path_pattern=file_path_pattern,
            recursive=recursive,
            exclude_patterns=exclude_patterns,
            exclude_dirs=exclude_directories,
            on_file_found=on_file_found  # This enables real-time feedback
        ):
            # The callback already prints the file, we don't need to do anything here
            pass
        
        # Report summary
        elapsed_time = time.time() - start_time
        print(f"\nSearch complete. Found {found_count} files in {elapsed_time:.2f} seconds.")
        
        return {
            "status": "success",
            "found_count": found_count,
            "elapsed_time": elapsed_time
        }


# Alternative approach - using the list version for simpler code
class SimpleExampleFindCommand(CommandBase):
    """
    Simpler example command using the list version of the file finder
    """
    
    name = "simpleExampleFind"
    description = "Simple example showing how to use the recursive file finding utility with list output"
    category = "file"
    
    # ... (same parameters and examples as ExampleFindCommand)
    
    def execute(self, directory='.', pattern='*', recursive=None, exclude=None, exclude_dir=None):
        """
        Execute the simple example command
        """
        # Process exclude patterns
        exclude_patterns = exclude.split(',') if exclude else []
        exclude_directories = exclude_dir.split(',') if exclude_dir else []
        
        # Build the full pattern
        file_path_pattern = os.path.join(directory, pattern)
        
        # Start timing
        start_time = time.time()
        
        # Get all files at once (no real-time feedback)
        print(f"Searching for files matching '{pattern}' in '{directory}'...")
        
        # Import the list version from the utility
        from Core.recursive_findfiles_utils import find_files_list
        
        # Get results all at once
        results = find_files_list(
            file_path_pattern=file_path_pattern,
            recursive=recursive,
            exclude_patterns=exclude_patterns,
            exclude_dirs=exclude_directories
        )
        
        # Print all results
        for file_path in results:
            print(f"Found: {file_path}")
        
        # Report summary
        elapsed_time = time.time() - start_time
        found_count = len(results)
        print(f"\nSearch complete. Found {found_count} files in {elapsed_time:.2f} seconds.")
        
        return {
            "status": "success",
            "found_count": found_count,
            "elapsed_time": elapsed_time
        } 