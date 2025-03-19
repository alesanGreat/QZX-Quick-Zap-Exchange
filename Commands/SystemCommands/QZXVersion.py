#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
QZXVersion Command - Displays the current version of QZX
"""

import os
import sys
import platform
from Core.command_base import CommandBase

class QZXVersionCommand(CommandBase):
    """
    Command to display the current version of QZX
    """
    
    name = "qzxVersion"
    description = "Displays the current version of QZX and system information"
    category = "system"
    
    parameters = []
    
    examples = [
        {
            'command': 'qzx qzxVersion',
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
            # This is a workaround - we hard-code the version here, but
            # in a real scenario, we would get it from the main class or a config file
            qzx_version = "0.02"
            
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
                # Try to get script path
                qzx_path = os.path.abspath(sys.argv[0])
                qzx_dir = os.path.dirname(qzx_path)
                qzx_info["install_path"] = qzx_dir
                qzx_info["executable"] = qzx_path
                
                # Try to get command count
                command_dirs = [
                    os.path.join(qzx_dir, "Commands/FileCommands"),
                    os.path.join(qzx_dir, "Commands/SystemCommands"),
                    os.path.join(qzx_dir, "Commands/DevCommands")
                ]
                
                command_count = 0
                for command_dir in command_dirs:
                    if os.path.exists(command_dir):
                        # Count Python files in the directory
                        command_count += len([f for f in os.listdir(command_dir) 
                                            if f.endswith('.py') and not f.startswith('__')])
                
                qzx_info["command_count"] = command_count
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