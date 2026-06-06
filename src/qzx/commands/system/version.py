#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Version Command - Displays the current version of QZX
"""

import platform
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from qzx.core.command_base import CommandBase
from qzx.core.command_loader import CommandLoader
from qzx import __version__

class QZXVersionCommand(CommandBase):
    """
    Command to display the current version of QZX
    """
    
    name = "version"
    aliases = ["qzxVersion"]
    description = "Displays the current version of QZX and system information"
    category = "system"
    
    parameters = []
    
    examples = [
        {
            'command': 'qzx version',
            'description': 'Display the current version of QZX and system information'
        }
    ]
    
    def execute(self):
        """
        Displays the current version of QZX
        
        Returns:
            Dictionary with version information
        """
        try:
            # Get the version from the main QZX class
            qzx_version = __version__
            
            # Gather additional system information
            system_info = {
                "os": platform.system(),
                "os_version": platform.version(),
                "os_release": platform.release(),
                "machine": platform.machine(),
                "processor": platform.processor(),
                "python_version": platform.python_version(),
                "python_implementation": platform.python_implementation()
            }
            
            # Get QZX installation information
            qzx_info = {}
            try:
                commands = CommandLoader().discover_commands()
                qzx_info["command_count"] = len(
                    {command.__name__ for command in commands.values()}
                )
            except:
                # Ignore errors in getting installation info
                pass
            
            # Create a readable summary for the message
            os_name = system_info.get("os", "Unknown OS")
            os_version = system_info.get("os_release", "")
            python_version = system_info.get("python_version", "Unknown")
            command_count_str = f"{qzx_info.get('command_count', 'Unknown')} commands" if "command_count" in qzx_info else "commands"

            # Message with verbose information
            message = f"QZX Version {qzx_version} running on {os_name} {os_version} with Python {python_version}. {command_count_str} available."
            
            # Prepare the result with explicit success indicator and message
            result = {
                "success": True,
                "message": message,
                "version": qzx_version,
                "system_info": system_info,
                "qzx_info": qzx_info
            }
            
            return result
        except Exception as e:
            # Return structured error with explicit failure indicator
            return {
                "success": False,
                "error": f"Error getting QZX version: {str(e)}",
                "message": f"Failed to retrieve QZX version information: {str(e)}"
            }
