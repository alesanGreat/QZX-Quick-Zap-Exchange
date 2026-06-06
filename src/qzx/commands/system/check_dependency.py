#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
CheckDependency Command - Checks if a dependency/executable is installed in the system PATH
"""

import os
import sys
import shutil
import subprocess
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from qzx.core.command_base import CommandBase

class CheckDependencyCommand(CommandBase):
    """
    Command to check if a dependency is installed and retrieve its version
    """
    
    name = "checkDependency"
    description = "Checks if a command-line dependency is installed in the system PATH and retrieves its version"
    category = "system"
    
    parameters = [
        {
            'name': 'dependency',
            'description': 'Name of the executable or dependency to check (e.g., git, node, docker)',
            'required': True
        }
    ]
    
    examples = [
        {
            'command': 'qzx checkDependency git',
            'description': 'Check if Git is installed and retrieve its version'
        },
        {
            'command': 'qzx checkDependency node',
            'description': 'Check if Node.js is installed'
        }
    ]
    
    def execute(self, dependency):
        """
        Checks if the dependency is installed
        
        Args:
            dependency (str): Name of the dependency/executable to search for
            
        Returns:
            Dictionary with installation status, version, and path
        """
        try:
            # Clean dependency name
            dependency = dependency.strip()
            if not dependency:
                return {
                    "success": False,
                    "error": "Dependency name cannot be empty."
                }
            
            # Find executable in PATH
            executable_path = shutil.which(dependency)
            
            if not executable_path:
                return {
                    "success": True,
                    "dependency": dependency,
                    "installed": False,
                    "message": f"Dependency '{dependency}' is not installed or not in the system PATH."
                }
                
            # Try to get the version
            version = None
            version_error = None
            
            # Try common version flags
            version_flags = ["--version", "-v", "-version", "version"]
            for flag in version_flags:
                try:
                    # Run subprocess with a short timeout
                    result = subprocess.run(
                        [dependency, flag],
                        capture_output=True,
                        text=True,
                        timeout=2.0,
                        check=False
                    )
                    
                    output = (result.stdout + "\n" + result.stderr).strip()
                    
                    # Look for version patterns like: 1.2.3, v1.2.3, 1.2, etc.
                    # A regex that matches typical version formats
                    version_match = re.search(r'(?:version\s+)?(v?\d+\.\d+(?:\.\d+)?(?:\-[a-zA-Z0-9\.]+)?(?:\+[a-zA-Z0-9\.]+)?(?:\s+\([^)]+\))?)', output, re.IGNORECASE)
                    
                    if version_match:
                        version = version_match.group(1).strip()
                        break
                    elif output and len(output) < 50 and any(c.isdigit() for c in output):
                        # Fallback for very simple outputs
                        version = output
                        break
                except (subprocess.SubprocessError, OSError) as e:
                    version_error = str(e)
                    continue
            
            # Prepare result
            result = {
                "success": True,
                "dependency": dependency,
                "installed": True,
                "executable_path": os.path.abspath(executable_path),
                "version": version
            }
            
            # Message formatting
            if version:
                result["message"] = f"Dependency '{dependency}' is installed (Version: {version}) at '{executable_path}'."
            else:
                result["message"] = f"Dependency '{dependency}' is installed at '{executable_path}', but its version could not be determined."
                if version_error:
                    result["version_error"] = version_error
                    
            return result
            
        except Exception as e:
            return {
                "success": False,
                "dependency": dependency,
                "error": str(e),
                "message": f"Failed to check dependency status: {str(e)}"
            }
