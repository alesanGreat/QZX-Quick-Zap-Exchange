#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
CleanDevCaches Command - Recursively scans for common development cache/dependency directories and cleans them.
"""

import os
import sys
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from qzx.core.command_base import CommandBase

class CleanDevCachesCommand(CommandBase):
    """
    Command to identify and clean up heavy development cache/dependency directories (e.g. node_modules, __pycache__).
    """
    
    name = "cleanDevCaches"
    description = "Scans recursively for heavy development caches/dependencies (node_modules, __pycache__, dist) and purges them"
    category = "development"
    
    parameters = [
        {
            'name': 'scan_path',
            'description': 'Path to start the scan from (defaults to current working directory)',
            'required': False,
            'default': '.'
        },
        {
            'name': 'dry_run',
            'description': 'If true, only lists files and space saved without deleting anything (true/false)',
            'required': False,
            'default': 'true'
        },
        {
            'name': 'max_depth',
            'description': 'Maximum folder depth to traverse recursively (defaults to 4)',
            'required': False,
            'default': '4'
        }
    ]
    
    examples = [
        {
            'command': 'qzx cleanDevCaches',
            'description': 'Scan the current directory for cache folders (dry run)'
        },
        {
            'command': 'qzx cleanDevCaches . false',
            'description': 'Scan the current directory and actually delete found cache folders'
        }
    ]
    
    # Target folder names that are safe to delete as development caches
    CACHE_TARGETS = {
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".next",
        ".nuxt",
        ".docusaurus",
        ".turbo",
        ".gradle",
        ".sass-cache",
        ".tscache"
    }
    
    # Target folder names that need safety verification before deletion
    CONDITIONAL_TARGETS = {
        "dist": ["package.json", "vite.config.js", "vite.config.ts", "webpack.config.js"],
        "build": ["package.json", "setup.py", "CMakeLists.txt"],
        "target": ["Cargo.toml"],
        "bin": ["*.csproj", "*.sln"],
        "obj": ["*.csproj", "*.sln"]
    }
    
    def execute(self, scan_path='.', dry_run='true', max_depth='4'):
        """
        Executes the cache scanning and cleaning
        
        Args:
            scan_path (str): The starting directory path
            dry_run (str/bool): Whether to skip actual deletion
            max_depth (str/int): Traversal depth limit
            
        Returns:
            Dictionary with results and details
        """
        abs_path = os.path.abspath(scan_path)
        
        if not os.path.exists(abs_path):
            return {
                "success": False,
                "error": f"Path '{scan_path}' does not exist.",
                "message": f"Path '{scan_path}' does not exist."
            }
            
        if not os.path.isdir(abs_path):
            return {
                "success": False,
                "error": f"'{scan_path}' is not a directory. Scanning requires a folder path.",
                "message": f"'{scan_path}' is not a directory."
            }
            
        # Parse arguments
        if isinstance(dry_run, str):
            is_dry_run = dry_run.lower() in ('true', 'yes', 'y', '1', 't')
        else:
            is_dry_run = bool(dry_run)
            
        try:
            depth_limit = int(max_depth)
        except ValueError:
            depth_limit = 4
            
        found_folders = []
        total_bytes = 0
        
        # Walk directories recursively up to depth_limit
        base_depth = abs_path.count(os.sep)
        
        try:
            for root, dirs, files in os.walk(abs_path, topdown=True):
                # Calculate current depth
                current_depth = root.count(os.sep) - base_depth
                if current_depth >= depth_limit:
                    # Clear subdirectories to stop traversing deeper
                    dirs.clear()
                    continue
                
                # Exclude standard version control to avoid entering them
                for skip_dir in [".git", ".svn", ".hg"]:
                    if skip_dir in dirs:
                        dirs.remove(skip_dir)
                        
                # Identify cache directories inside the current root
                matched_dirs = []
                for d in list(dirs):
                    full_d_path = os.path.join(root, d)
                    is_match = False
                    reason = ""
                    
                    # Direct match
                    if d in self.CACHE_TARGETS:
                        is_match = True
                        reason = f"Direct cache target name '{d}'"
                    # Conditional match (safety verification check)
                    elif d in self.CONDITIONAL_TARGETS:
                        triggers = self.CONDITIONAL_TARGETS[d]
                        # Check if any trigger files exist in the parent folder (root)
                        for trigger in triggers:
                            if "*" in trigger:
                                # wildcard match
                                import fnmatch
                                if any(fnmatch.fnmatch(f, trigger) for f in files):
                                    is_match = True
                                    reason = f"Conditional target '{d}' matched by file pattern '{trigger}'"
                                    break
                            else:
                                if trigger in files:
                                    is_match = True
                                    reason = f"Conditional target '{d}' matched by parent file '{trigger}'"
                                    break
                                    
                    if is_match:
                        # Add to matches and remove from dirs to prevent walking inside it
                        matched_dirs.append((full_d_path, d, reason))
                        dirs.remove(d)
                        
                for full_path, name, reason in matched_dirs:
                    size = self._get_dir_size(full_path)
                    found_folders.append({
                        "path": full_path,
                        "relative_path": os.path.relpath(full_path, abs_path),
                        "name": name,
                        "reason": reason,
                        "size_bytes": size,
                        "size_readable": self._format_bytes(size)
                    })
                    total_bytes += size
                    
            # Perform deletion if not dry_run
            deleted_folders = []
            errors = []
            
            if not is_dry_run:
                for item in found_folders:
                    target_path = item["path"]
                    try:
                        shutil.rmtree(target_path)
                        deleted_folders.append(target_path)
                    except Exception as e:
                        errors.append(f"Failed to delete '{target_path}': {str(e)}")
            
            # Formulate the response message
            readable_total = self._format_bytes(total_bytes)
            action_type = "Dry-run scan" if is_dry_run else "Clean operation"
            
            msg = f"{action_type} completed for '{abs_path}':\n"
            msg += f"- Identified cache folders: {len(found_folders)}\n"
            msg += f"- Total space: {readable_total}\n"
            
            if not is_dry_run:
                msg += f"- Successfully deleted: {len(deleted_folders)}\n"
                if errors:
                    msg += f"- Deletion errors encountered: {len(errors)}\n"
            else:
                msg += "- Note: This was a dry run. No folders were deleted. Run with dry_run=false to delete.\n"
                
            return {
                "success": True,
                "scan_path": abs_path,
                "dry_run": is_dry_run,
                "total_folders_found": len(found_folders),
                "total_bytes_saved": total_bytes,
                "total_space_saved_readable": readable_total,
                "found_folders": found_folders,
                "deleted_folders": deleted_folders,
                "errors": errors,
                "message": msg
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to execute cache cleaning: {str(e)}"
            }
            
    def _get_dir_size(self, path):
        """Calculates total size of a directory in bytes"""
        total_size = 0
        try:
            for root, _, files in os.walk(path):
                for f in files:
                    fp = os.path.join(root, f)
                    try:
                        if not os.path.islink(fp):
                            total_size += os.path.getsize(fp)
                    except OSError:
                        pass
        except Exception:
            pass
        return total_size
        
    def _format_bytes(self, size):
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0 or unit == 'TB':
                break
            size /= 1024.0
        return f"{size:.2f} {unit}"
