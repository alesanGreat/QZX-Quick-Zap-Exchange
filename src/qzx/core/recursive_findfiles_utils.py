#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Recursive File Finder Utility - Centralizes recursive file search functionality for QZX commands

This module provides functions to search for files recursively with support for
wildcards, excluding specific directories and with callbacks for real-time reporting.
"""

import os
import re
import fnmatch
import glob
from typing import Callable, Generator, List, Optional

def parse_recursive_parameter(recursive_param) -> Optional[int]:
    """
    Parse the recursive parameter into a depth value
    
    Args:
        recursive_param: The raw recursive parameter (string or bool)
        
    Returns:
        int or None: Maximum recursion depth (None for unlimited, 0 for none)
    """
    try:
        # Default is no recursion (0) if parameter is None
        if recursive_param is None:
            return 0
            
        # If it's a boolean
        if isinstance(recursive_param, bool):
            return None if recursive_param else 0
            
        # If it's directly an integer
        if isinstance(recursive_param, int):
            return max(0, recursive_param)  # Ensure it's not negative
            
        # If it's a string, only support flag formats
        if isinstance(recursive_param, str):
            # Convert to lowercase for standardization
            recursive_param = recursive_param.lower()
            
            # Parse -r or --recursive format
            if recursive_param in ('-r', '--recursive', '-R'):
                return None  # Unlimited recursion
                
            # Try to parse -rN format (e.g. -r3)
            r_depth_match = re.match(r'^-r(\d+)$', recursive_param)
            if r_depth_match:
                return int(r_depth_match.group(1))
            
            # Try to parse --recursiveN format (e.g. --recursive3)
            recursive_match = re.match(r'^--recursive(\d+)$', recursive_param)
            if recursive_match:
                return int(recursive_match.group(1))
        
        # If it doesn't match any known format, use the default (no recursion)
        return 0
    except Exception:
        # In case of any exception, return the default
        return 0


def find_files(
    file_path_pattern: str, 
    recursive=False, 
    max_depth: Optional[int] = None,
    exclude_patterns: Optional[List[str]] = None,
    exclude_dirs: Optional[List[str]] = None,
    file_type: Optional[str] = None,
    on_file_found: Optional[Callable[[str], None]] = None,
    on_dir_found: Optional[Callable[[str], None]] = None
) -> Generator[str, None, None]:
    """
    Find files or directories that match a pattern and return them one by one.
    
    Args:
        file_path_pattern (str): Path pattern to search for (can include wildcards)
        recursive (bool): Whether to search recursively in directories
        file_type (str): 'f' for files, 'd' for directories, None for both
        max_depth (int): Maximum recursion depth (only used if recursive is True)
        
    Yields:
        str: Paths of matching files or directories
    """
    exclude_patterns = exclude_patterns or []
    exclude_dirs = exclude_dirs or []

    # Add debug output
    #print(f"DEBUG: find_files called with file_path_pattern={file_path_pattern}, recursive={recursive}, type={type(recursive)}")
    
    # Normalize recursion to 0 (none), None (unlimited), or a positive depth.
    if isinstance(recursive, str):
        recursion_depth = parse_recursive_parameter(recursive)
    elif recursive is True:
        recursion_depth = None
    elif recursive is None:
        recursion_depth = None
    elif isinstance(recursive, int):
        recursion_depth = max(0, recursive)
    else:
        recursion_depth = 0

    if max_depth is not None:
        max_depth = max(0, int(max_depth))
        if recursion_depth is None:
            recursion_depth = max_depth
        elif recursion_depth > 0:
            recursion_depth = min(recursion_depth, max_depth)
    
    #print(f"DEBUG: After parse_recursive_parameter, max_depth={max_depth}")
    
    # The pattern can include a directory path and a filename pattern
    # Split them properly to search in the right place
    file_path_pattern = file_path_pattern.replace('\\', '/')
    
    # Handle special case: if the pattern is just a directory
    if os.path.isdir(file_path_pattern):
        directory = file_path_pattern
        pattern = '*'
    else:
        # Normal case: split into directory and pattern
        directory = os.path.dirname(file_path_pattern)
        pattern = os.path.basename(file_path_pattern)
        
        # If the directory is empty, use the current directory
        if not directory:
            directory = '.'
    
    #print(f"DEBUG: Extracted directory={directory}, pattern={pattern}")
            
    # Convert directory to absolute path
    directory = os.path.abspath(directory)
    
    recursive_enabled = recursion_depth is None or recursion_depth > 0

    # If not recursive, use simple glob.
    if not recursive_enabled:
        for file_path in glob.glob(os.path.join(directory, pattern)):
            filename = os.path.basename(file_path)
            if any(
                fnmatch.fnmatch(filename, exclude_pattern)
                for exclude_pattern in exclude_patterns
            ):
                continue

            if file_type is None or \
               (file_type == 'f' and os.path.isfile(file_path)) or \
               (file_type == 'd' and os.path.isdir(file_path)):
                
                # Call the appropriate callback if provided
                if os.path.isfile(file_path) and on_file_found:
                    on_file_found(file_path)
                elif os.path.isdir(file_path) and on_dir_found:
                    on_dir_found(file_path)
                
                # Yield the path
                yield file_path
    else:
        # Do a recursive search using os.walk
        #print(f"DEBUG: Using recursive os.walk with max_depth={max_depth}")
        
        for root, dirs, files in os.walk(directory):
            relative_root = os.path.relpath(root, directory)
            current_depth = 0 if relative_root == "." else relative_root.count(os.sep) + 1

            excluded_dirs = {
                dirname
                for dirname in dirs
                if any(
                    fnmatch.fnmatch(dirname, exclude_pattern)
                    for exclude_pattern in exclude_dirs
                )
            }
            dirs[:] = [dirname for dirname in dirs if dirname not in excluded_dirs]
            
            # Check if we've reached the maximum depth
            if recursion_depth is not None and current_depth >= recursion_depth:
                #print(f"DEBUG: Reached max depth {max_depth} at {root}, stopping deeper search")
                # Clear dirs list to prevent further recursion
                dirs.clear()
            
            matched_files = []
            matched_dirs = []
            
            # Filter matches based on the pattern and type
            if file_type is None or file_type == 'f':
                matched_files = [
                    filename
                    for filename in fnmatch.filter(files, pattern)
                    if not any(
                        fnmatch.fnmatch(filename, exclude_pattern)
                        for exclude_pattern in exclude_patterns
                    )
                ]
            
            if file_type is None or file_type == 'd':
                matched_dirs = fnmatch.filter(dirs, pattern)
            
            #print(f"DEBUG: Found {len(matched_files)} matching files in {root}")
            
            # Yield matching files
            for filename in matched_files:
                file_path = os.path.join(root, filename)
                
                #print(f"DEBUG: Yielding file {file_path}")
                
                # Call the callback if provided
                if on_file_found:
                    on_file_found(file_path)
                
                yield file_path
            
            #print(f"DEBUG: Found {len(matched_dirs)} matching directories in {root}")
            
            # Yield matching directories
            for dirname in matched_dirs:
                dir_path = os.path.join(root, dirname)
                
                #print(f"DEBUG: Yielding directory {dir_path}")
                
                # Call the callback if provided
                if on_dir_found:
                    on_dir_found(dir_path)
                
                yield dir_path
            


def _check_file_matches(
    file_path: str, 
    file_type: Optional[str], 
    exclude_patterns: List[str],
    exclude_dirs: List[str],
    max_depth: Optional[int] = None,
    base_dir: Optional[str] = None
) -> bool:
    """Check if a file matches the criteria (type, exclusions, depth)"""
    # Check file type
    if (file_type == 'f' and not os.path.isfile(file_path)) or \
       (file_type == 'd' and not os.path.isdir(file_path)):
        return False
    
    # Check filename exclusions
    filename = os.path.basename(file_path)
    if any(fnmatch.fnmatch(filename.lower(), p) for p in exclude_patterns):
        return False
    
    # Check directory exclusions
    dir_path = os.path.dirname(file_path)
    if any(d in dir_path.lower() for p in exclude_dirs for d in dir_path.lower().split(os.sep)):
        return False
    
    # Check depth if applicable
    if max_depth is not None and base_dir is not None:
        current_depth = file_path.count(os.sep) - base_dir.rstrip(os.sep).count(os.sep)
        if current_depth > max_depth:
            return False
    
    return True


def find_files_list(
    file_path_pattern: str, 
    recursive=False, 
    max_depth: Optional[int] = None,
    exclude_patterns: Optional[List[str]] = None,
    exclude_dirs: Optional[List[str]] = None,
    file_type: Optional[str] = None,
    on_file_found: Optional[Callable[[str], None]] = None
) -> List[str]:
    """
    Version of find_files that returns a list instead of a generator
    
    Args:
        Same as find_files
        
    Returns:
        list: List of file paths matching the pattern
    """
    return list(find_files(
        file_path_pattern=file_path_pattern,
        recursive=recursive,
        max_depth=max_depth,
        exclude_patterns=exclude_patterns,
        exclude_dirs=exclude_dirs,
        file_type=file_type,
        on_file_found=on_file_found
    ))
