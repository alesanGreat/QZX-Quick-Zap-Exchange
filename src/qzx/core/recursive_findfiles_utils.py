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
from typing import Callable, Generator, List, Optional

from qzx.core.file_search_entries import direct_matches, prune_directory_references


# Source-analysis commands should inspect authored code, not dependency,
# environment, cache, coverage, or generated-output trees.  Keeping this list
# here gives every recursive analyzer the same cross-platform boundary while
# leaving the generic ``find_files`` helper opt-in.
SOURCE_ANALYSIS_EXCLUDED_DIRECTORIES = (
    ".angular",
    ".git",
    ".gradle",
    ".hg",
    ".idea",
    ".mypy_cache",
    ".next",
    ".nox",
    ".nuxt",
    ".pytest_cache",
    ".ruff_cache",
    ".svn",
    ".svelte-kit",
    ".tox",
    ".turbo",
    ".venv",
    ".vscode",
    "__pycache__",
    "bower_components",
    "build",
    "coverage",
    "dist",
    "env",
    "node_modules",
    "target",
    "venv",
    "vendor",
)


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
    on_dir_found: Optional[Callable[[str], None]] = None,
    on_error: Optional[Callable[[OSError], None]] = None,
    *,
    recursive_walker=os.walk,
    direct_matcher=direct_matches,
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
    recursion_depth = _recursion_depth(recursive, max_depth)
    directory, pattern = _search_location(file_path_pattern)
    options = {
        "directory": directory,
        "pattern": pattern,
        "file_type": file_type,
        "exclude_patterns": exclude_patterns or [],
        "exclude_dirs": exclude_dirs or [],
        "on_file_found": on_file_found,
        "on_dir_found": on_dir_found,
        "on_error": on_error,
    }
    if recursion_depth is None or recursion_depth > 0:
        yield from _iter_recursive_matches(
            recursion_depth=recursion_depth,
            recursive_walker=recursive_walker,
            **options,
        )
    else:
        yield from _iter_direct_matches(
            direct_matcher=direct_matcher,
            **options,
        )


def _recursion_depth(recursive, max_depth):
    """Normalize recursion to zero, unlimited, or a positive depth."""
    if isinstance(recursive, str):
        depth = parse_recursive_parameter(recursive)
    elif recursive is True or recursive is None:
        depth = None
    elif isinstance(recursive, int):
        depth = max(0, recursive)
    else:
        depth = 0
    if max_depth is None:
        return depth
    maximum = max(0, int(max_depth))
    if depth is None:
        return maximum
    return min(depth, maximum) if depth > 0 else depth


def _search_location(file_path_pattern):
    """Split one user pattern into an absolute directory and basename glob."""
    normalized = file_path_pattern.replace('\\', '/')
    if os.path.isdir(normalized):
        return os.path.abspath(normalized), '*'
    directory = os.path.dirname(normalized) or '.'
    return os.path.abspath(directory), os.path.basename(normalized)


def _matches_requested_type(path, file_type):
    return (
        file_type is None
        or file_type == 'f' and os.path.isfile(path)
        or file_type == 'd' and os.path.isdir(path)
    )


def _iter_direct_matches(
    directory, pattern, file_type, exclude_patterns, exclude_dirs,
    on_file_found, on_dir_found, on_error, direct_matcher,
):
    del exclude_dirs  # Directory pruning applies only to recursive traversal.
    yield from direct_matcher(
        directory, pattern, file_type, exclude_patterns,
        on_file_found, on_dir_found, on_error,
    )


def _prune_directories(directories, exclude_dirs):
    excluded = {
        name for name in directories
        if any(fnmatch.fnmatch(name, pattern) for pattern in exclude_dirs)
    }
    directories[:] = [name for name in directories if name not in excluded]


def _matching_names(names, pattern, exclusions=()):
    return [
        name for name in fnmatch.filter(names, pattern)
        if not any(fnmatch.fnmatch(name, excluded) for excluded in exclusions)
    ]


def _yield_recursive_paths(root, matched_files, matched_dirs, callbacks):
    on_file_found, on_dir_found = callbacks
    for filename in matched_files:
        path = os.path.join(root, filename)
        if on_file_found:
            on_file_found(path)
        yield path
    for dirname in matched_dirs:
        path = os.path.join(root, dirname)
        if on_dir_found:
            on_dir_found(path)
        yield path


def _iter_recursive_matches(
    directory, pattern, file_type, exclude_patterns, exclude_dirs,
    on_file_found, on_dir_found, recursion_depth, on_error, recursive_walker,
):
    for root, directories, files in recursive_walker(
        directory, onerror=on_error, followlinks=False
    ):
        relative_root = os.path.relpath(root, directory)
        current_depth = 0 if relative_root == "." else relative_root.count(os.sep) + 1
        _prune_directories(directories, exclude_dirs)
        if recursion_depth is not None and current_depth >= recursion_depth:
            directories.clear()
        matched_files = (
            _matching_names(files, pattern, exclude_patterns)
            if file_type is None or file_type == 'f' else []
        )
        matched_dirs = (
            _matching_names(directories, pattern)
            if file_type is None or file_type == 'd' else []
        )
        prune_directory_references(root, directories, on_error)
        yield from _yield_recursive_paths(
            root, matched_files, matched_dirs,
            (on_file_found, on_dir_found),
        )
            


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
