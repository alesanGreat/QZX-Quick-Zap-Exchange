#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
SystemInfo Command - Retrieves information about the operating system
"""

import os
import platform
import sys
from Core.command_base import CommandBase

class SystemInfoCommand(CommandBase):
    """
    Command to get system information
    """
    
    name = "systemInfo"
    description = "Gets information about the operating system and environment"
    category = "system"
    
    parameters = []
    
    examples = [
        {
            'command': 'qzx systemInfo',
            'description': 'Get detailed information about the system'
        }
    ]
    
    def execute(self):
        """
        Gets system information
        
        Returns:
            Dictionary with system information
        """
        try:
            # Collect system information
            info = {
                "os": platform.system(),
                "os_version": platform.version(),
                "os_release": platform.release(),
                "machine": platform.machine(),
                "processor": platform.processor(),
                "architecture": platform.architecture(),
                "platform": sys.platform,
                "python": {
                    "version": platform.python_version(),
                    "implementation": platform.python_implementation(),
                    "compiler": platform.python_compiler(),
                    "build": platform.python_build()
                },
                "network": {
                    "hostname": platform.node()
                },
                "user": {
                    "username": os.getlogin(),
                    "home_directory": os.path.expanduser("~")
                },
                "environment": {
                    "current_directory": os.getcwd(),
                    "environment_variables": self._get_important_env_vars()
                }
            }
            
            # Try to get more detailed OS information
            if platform.system() == "Windows":
                try:
                    # Add Windows-specific information
                    windows_info = {
                        "edition": platform.win32_edition(),
                        "version": platform.win32_ver()
                    }
                    info["windows"] = windows_info
                except:
                    pass
            
            elif platform.system() == "Linux":
                try:
                    # Add Linux-specific information
                    linux_info = {
                        "distribution": platform.linux_distribution(),
                        "libc_ver": platform.libc_ver()
                    }
                    info["linux"] = linux_info
                except:
                    pass
            
            elif platform.system() == "Darwin":  # macOS
                try:
                    # Add macOS-specific information
                    mac_info = {
                        "version": platform.mac_ver()
                    }
                    info["macos"] = mac_info
                except:
                    pass
            
            # Create a detailed message for verbose output
            os_name = info.get("os", "Unknown OS")
            os_version = info.get("os_version", "")
            os_release = info.get("os_release", "")
            machine = info.get("machine", "Unknown architecture")
            processor = info.get("processor", "Unknown processor")
            python_version = info["python"].get("version", "Unknown")
            python_impl = info["python"].get("implementation", "Unknown")
            hostname = info["network"].get("hostname", "Unknown host")
            username = info["user"].get("username", "Unknown user")
            
            # Build a comprehensive message with the most important system details
            message = (
                f"System running {os_name} {os_release} ({os_version}) on {machine} architecture. "
                f"Processor: {processor}. "
                f"Python {python_impl} {python_version}. "
                f"Hostname: {hostname}, logged in as {username}."
            )
            
            # Add extra OS-specific details if available
            if "windows" in info:
                win_edition = info["windows"].get("edition", "")
                if win_edition:
                    message += f" Windows edition: {win_edition}."
            
            # Return the result with success flag and message
            result = {
                "success": True,
                "message": message,
                "system_info": info
            }
            
            return result
        except Exception as e:
            return {
                "success": False,
                "error": f"Error getting system information: {str(e)}",
                "message": f"Failed to retrieve system information: {str(e)}"
            }
    
    def _get_important_env_vars(self):
        """
        Get important environment variables
        
        Returns:
            Dictionary with selected environment variables
        """
        # List of important environment variables to include
        important_vars = [
            "PATH", "PYTHONPATH", "LANG", "USER", "HOME", "TEMP", "TMP",
            "SHELL", "LOGNAME", "USERNAME", "COMPUTERNAME", "HOSTNAME"
        ]
        
        env_vars = {}
        for var in important_vars:
            if var in os.environ:
                env_vars[var] = os.environ[var]
        
        return env_vars 