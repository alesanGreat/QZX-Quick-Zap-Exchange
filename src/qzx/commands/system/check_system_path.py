#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
CheckSystemPath Command - Diagnoses system PATH environment variable health and locates duplicate binary executables.
"""

import os
import sys
import platform
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from qzx.core.command_base import CommandBase

class CheckSystemPathCommand(CommandBase):
    """
    Command to inspect PATH environment variable health, check for invalid or duplicate directories, and resolve command conflicts.
    """
    
    name = "checkSystemPath"
    description = "Diagnoses the system PATH variable, lists broken or duplicate folders, and locates all instances of a binary"
    category = "system"
    
    parameters = [
        {
            'name': 'binary_name',
            'description': 'Optional binary name to search for (e.g. python, node, git)',
            'required': False,
            'default': ''
        }
    ]
    
    examples = [
        {
            'command': 'qzx checkSystemPath',
            'description': 'Inspect system PATH directories for duplicates, errors, and invalid folder paths'
        },
        {
            'command': 'qzx checkSystemPath python',
            'description': 'Diagnose PATH and list all physical locations of python executables, in order of execution precedence'
        }
    ]
    
    def execute(self, binary_name=''):
        """
        Diagnoses PATH and optional binary locations
        
        Args:
            binary_name (str, optional): Name of executable to find
            
        Returns:
            Dictionary with PATH analysis and executable locations
        """
        is_windows = platform.system().lower() == "windows"
        path_sep = ";" if is_windows else ":"
        
        # Get path environment string
        path_env = os.environ.get("PATH", "")
        if not path_env:
            return {
                "success": False,
                "error": "PATH environment variable is empty or not set.",
                "message": "PATH environment variable is empty."
            }
            
        path_dirs = path_env.split(path_sep)
        
        valid_dirs = []
        broken_dirs = []
        duplicate_dirs = []
        seen = set()
        
        for index, d in enumerate(path_dirs):
            d = d.strip()
            if not d:
                continue
                
            # Clean quotes if any (Windows paths sometimes have quotes)
            if d.startswith('"') and d.endswith('"'):
                d = d[1:-1]
                
            norm_d = os.path.normpath(os.path.abspath(d))
            norm_d_lower = norm_d.lower() if is_windows else norm_d
            
            # Check duplicate
            if norm_d_lower in seen:
                duplicate_dirs.append({
                    "index": index,
                    "raw_path": d,
                    "resolved_path": norm_d
                })
                continue
                
            seen.add(norm_d_lower)
            
            # Check existence and is directory
            if os.path.exists(norm_d):
                if os.path.isdir(norm_d):
                    valid_dirs.append({
                        "index": index,
                        "raw_path": d,
                        "resolved_path": norm_d
                    })
                else:
                    broken_dirs.append({
                        "index": index,
                        "raw_path": d,
                        "resolved_path": norm_d,
                        "reason": "Path exists but is a file, not a directory."
                    })
            else:
                broken_dirs.append({
                    "index": index,
                    "raw_path": d,
                    "resolved_path": norm_d,
                    "reason": "Directory does not exist."
                })
                
        # Resolve executables if binary_name is provided
        bin_search = binary_name.strip()
        binary_matches = []
        
        if bin_search:
            # Determine potential extensions to search
            extensions = [""]
            if is_windows:
                # Add default Windows execution extensions
                exts = [".exe", ".cmd", ".bat", ".ps1", ".lnk"]
                # If target already has an extension, prioritize it first
                _, target_ext = os.path.splitext(bin_search.lower())
                if target_ext in exts:
                    extensions = [""]
                else:
                    extensions = exts + [""]
                    
            for item in valid_dirs:
                d_path = item["resolved_path"]
                for ext in extensions:
                    file_name = bin_search + ext
                    full_file_path = os.path.join(d_path, file_name)
                    
                    try:
                        # Check if file exists, is a file, and is executable
                        if os.path.isfile(full_file_path):
                            # Try executing permissions
                            is_executable = os.access(full_file_path, os.X_OK)
                            
                            # On Windows, os.access(..., os.X_OK) might return True for non-executable files,
                            # but filtering by standard extensions (which we did) covers it.
                            if is_executable or is_windows:
                                binary_matches.append({
                                    "path_index": item["index"],
                                    "directory": d_path,
                                    "filename": file_name,
                                    "full_path": full_file_path,
                                    "size_bytes": os.path.getsize(full_file_path)
                                })
                                # Stop trying other extensions once we find one match in this folder
                                break
                    except Exception:
                        pass
                        
        # Formulate output message
        msg = "PATH Diagnostics Summary:\n"
        msg += f"- Total entries in PATH: {len(path_dirs)}\n"
        msg += f"- Valid directories: {len(valid_dirs)}\n"
        msg += f"- Broken paths: {len(broken_dirs)}\n"
        msg += f"- Duplicate entries: {len(duplicate_dirs)}\n"
        
        if broken_dirs:
            msg += "\n[WARNING] Broken entries identified:\n"
            for b in broken_dirs[:5]:
                msg += f"  - Index {b['index']}: '{b['raw_path']}' ({b['reason']})\n"
            if len(broken_dirs) > 5:
                msg += f"  ... and {len(broken_dirs) - 5} more.\n"
                
        if bin_search:
            msg += f"\nBinary resolution search for '{bin_search}':\n"
            if binary_matches:
                msg += f"- Found {len(binary_matches)} location(s) on PATH:\n"
                for index, match in enumerate(binary_matches):
                    prefix = "  >>> [First choice]" if index == 0 else "      [Shadowed]"
                    msg += f"{prefix} {match['full_path']}\n"
            else:
                msg += f"- [ERROR] No executables named '{bin_search}' found on current PATH.\n"
                
        return {
            "success": True,
            "binary_searched": bin_search or None,
            "path_summary": {
                "total_entries": len(path_dirs),
                "valid_count": len(valid_dirs),
                "broken_count": len(broken_dirs),
                "duplicate_count": len(duplicate_dirs)
            },
            "broken_paths": broken_dirs,
            "duplicate_paths": duplicate_dirs,
            "binary_matches": binary_matches,
            "message": msg
        }
