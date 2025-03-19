#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
GetCurrentUser Command - Retrieves information about the currently logged in user
"""

import os
import getpass
import psutil
from Core.command_base import CommandBase

class GetCurrentUserCommand(CommandBase):
    """
    Command to get information about the currently logged in user
    """
    
    name = "getCurrentUser"
    description = "Gets information about the currently logged in user"
    category = "system"
    
    parameters = []
    
    examples = [
        {
            'command': 'qzx getCurrentUser',
            'description': 'Get detailed information about the currently logged in user'
        }
    ]
    
    def execute(self):
        """
        Gets information about the currently logged in user
        
        Returns:
            Dictionary with user information and operation status
        """
        try:
            result = {
                "username": None,
                "home_directory": os.path.expanduser("~"),
                "environment_variables": {},
                "processes": {}
            }
            
            # Get basic user information
            try:
                result["username"] = getpass.getuser()
            except:
                try:
                    result["username"] = os.getlogin()
                except:
                    result["username"] = "Unknown"
            
            # Get environment variables related to the user
            user_env_vars = {
                "USER": os.environ.get("USER"),
                "USERNAME": os.environ.get("USERNAME"),
                "USERPROFILE": os.environ.get("USERPROFILE"),
                "HOME": os.environ.get("HOME"),
                "LOGNAME": os.environ.get("LOGNAME")
            }
            
            # Filter out None values and add to result
            result["environment_variables"] = {k: v for k, v in user_env_vars.items() if v is not None}
            
            # Get shell information
            shell = os.environ.get("SHELL", os.environ.get("COMSPEC"))
            if shell:
                result["shell"] = shell
            
            # Get additional user info if psutil is available
            try:
                current_process = psutil.Process()
                
                if hasattr(current_process, 'username'):
                    user_id = current_process.username()
                    result["user_id"] = user_id
                
                # Get the user's processes count and memory usage
                try:
                    user_processes = [p for p in psutil.process_iter(['username', 'memory_info']) 
                                      if hasattr(p, 'info') and p.info.get('username') == result["username"]]
                    
                    result["processes"] = {
                        "count": len(user_processes),
                        "total_memory_usage": sum(p.info.get('memory_info').rss if p.info.get('memory_info') else 0 
                                                 for p in user_processes)
                    }
                    
                    # Add readable format for memory usage
                    if "total_memory_usage" in result["processes"]:
                        result["processes"]["total_memory_usage_readable"] = self._format_bytes(
                            result["processes"]["total_memory_usage"]
                        )
                except:
                    pass
            except:
                pass  # Skip if psutil features are not available
            
            # Try to get current working directory
            try:
                result["current_directory"] = os.getcwd()
            except:
                pass
            
            # Create a detailed message about the user
            username = result.get("username", "Unknown")
            home_dir = result.get("home_directory", "Unknown")
            shell_info = result.get("shell", "Unknown shell")
            process_count = result.get("processes", {}).get("count", 0)
            memory_usage = result.get("processes", {}).get("total_memory_usage_readable", "Unknown")
            
            # Build a comprehensive message
            message = f"Current user: {username}. Home directory: {home_dir}. Shell: {shell_info}."
            
            # Add process information if available
            if process_count > 0:
                message += f" User has {process_count} running processes using {memory_usage} of memory."
            
            # Add the message and success flag to the result
            result["success"] = True
            result["message"] = message
            
            return result
        except Exception as e:
            error_message = f"Error getting current user information: {str(e)}"
            return {
                "success": False,
                "error": error_message,
                "message": f"Failed to retrieve current user information: {str(e)}"
            }
    
    def _format_bytes(self, bytes_value):
        """
        Format bytes to human-readable format
        
        Args:
            bytes_value (int): Bytes to format
            
        Returns:
            str: Formatted string with appropriate unit
        """
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_value < 1024 or unit == 'TB':
                return f"{bytes_value:.2f} {unit}"
            bytes_value /= 1024 