#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
FindBrokenSymlinks Command - Scans directories recursively for symbolic links pointing to deleted/missing targets.
"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

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
        """
        Scans for broken symlinks
        
        Args:
            folder_path (str): Starting folder
            max_depth (str/int): Folder depth limit
            
        Returns:
            Dictionary with list of broken symlinks
        """
        abs_path = os.path.abspath(folder_path)
        
        if not os.path.exists(abs_path):
            return {
                "success": False,
                "error": f"Path '{folder_path}' does not exist.",
                "message": f"Path '{folder_path}' does not exist."
            }
            
        if not os.path.isdir(abs_path):
            return {
                "success": False,
                "error": f"'{folder_path}' is not a directory.",
                "message": f"'{folder_path}' is not a directory."
            }
            
        try:
            depth_limit = int(max_depth)
        except ValueError:
            depth_limit = 4
            
        broken_symlinks = []
        base_depth = abs_path.count(os.sep)
        
        try:
            # Walk directory tree
            for root, dirs, files in os.walk(abs_path, topdown=True):
                current_depth = root.count(os.sep) - base_depth
                if current_depth >= depth_limit:
                    dirs.clear()
                    continue
                    
                # Skip heavy dirs
                for skip in [".git", "node_modules", ".venv", "env"]:
                    if skip in dirs:
                        dirs.remove(skip)
                        
                # Check both directories and files for symlink status
                # (since Windows supports directory junctions/symlinks, and Unix supports folder symlinks)
                all_items = [os.path.join(root, d) for d in dirs] + [os.path.join(root, f) for f in files]
                
                for path in all_items:
                    try:
                        # os.path.islink checks if path is a symlink.
                        # Reparse points like directory junctions on Windows might not always trigger islink,
                        # but standard symlinks do. Let's do a cross-platform check.
                        is_link = os.path.islink(path)
                        
                        # In Python, os.path.exists returns False for broken symlinks
                        # because it attempts to follow the symlink to the target.
                        if is_link and not os.path.exists(path):
                            target = "unknown"
                            try:
                                target = os.readlink(path)
                            except Exception:
                                pass
                                
                            broken_symlinks.append({
                                "path": path,
                                "relative_path": os.path.relpath(path, abs_path),
                                "target": target
                            })
                    except OSError:
                        pass
                        
            total_found = len(broken_symlinks)
            msg = f"Broken symlinks scan completed for '{abs_path}':\n"
            msg += f"- Broken symlinks identified: {total_found}\n"
            
            if total_found > 0:
                msg += "\nDetected Broken Symlinks:\n"
                for index, item in enumerate(broken_symlinks[:10]):
                    msg += f"  - Index {index}: '{item['relative_path']}' -> points to missing '{item['target']}'\n"
                if total_found > 10:
                    msg += f"  ... and {total_found - 10} more.\n"
                msg += "\nNote: You can remove these broken symlinks safely to clean up path configurations."
            else:
                msg += "- Status: Clean. No broken symlinks found."
                
            return {
                "success": True,
                "scan_path": abs_path,
                "broken_symlinks_count": total_found,
                "broken_symlinks": broken_symlinks,
                "message": msg
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to search for broken symlinks: {str(e)}"
            }
