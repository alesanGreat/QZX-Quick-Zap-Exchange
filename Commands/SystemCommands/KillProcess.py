#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
KillProcess Command - Terminates a process by PID
"""

import platform
from Core.command_base import CommandBase

class KillProcessCommand(CommandBase):
    """
    Command to terminate a process by PID
    """
    
    name = "killProcess"
    description = "Terminates a process by its ID (similar to 'kill' in Unix)"
    category = "system"
    
    parameters = [
        {
            'name': 'pid',
            'description': 'Process ID to terminate',
            'required': True
        },
        {
            'name': 'force',
            'description': 'Whether to force termination (like kill -9)',
            'required': False,
            'default': False
        }
    ]
    
    examples = [
        {
            'command': 'qzx killProcess 1234',
            'description': 'Terminate the process with PID 1234'
        },
        {
            'command': 'qzx killProcess 1234 true',
            'description': 'Force terminate the process with PID 1234'
        }
    ]
    
    def execute(self, pid, force=False):
        """
        Terminates a process by PID
        
        Args:
            pid (int): Process ID to terminate
            force (bool, optional): Whether to force termination
            
        Returns:
            Dictionary with the operation result and status
        """
        # Import psutil here to avoid errors during module loading if not installed
        try:
            import psutil
        except ImportError:
            return {
                "success": False,
                "error": "The psutil module is required for this command. Install it with: pip install psutil",
                "message": "Failed to terminate process: psutil module is not installed. Please install it with: pip install psutil"
            }
        
        try:
            # Convert PID to integer
            try:
                pid = int(pid)
            except ValueError:
                return {
                    "success": False,
                    "error": f"PID must be an integer, received '{pid}'",
                    "message": f"Failed to terminate process: PID must be an integer, but received '{pid}'"
                }
            
            # Convert force to boolean if it's a string
            if isinstance(force, str):
                force = force.lower() in ('true', 'yes', 'y', '1')
            
            # Check if the process exists
            if not psutil.pid_exists(pid):
                return {
                    "success": False,
                    "error": f"No process found with PID {pid}",
                    "message": f"Failed to terminate process: No process found with PID {pid}"
                }
            
            # Get the process
            process = psutil.Process(pid)
            
            # Get process information for the output message
            try:
                process_name = process.name()
                process_username = process.username()
                process_cmdline = process.cmdline()
                process_create_time = process.create_time()
                process_exe = process.exe()
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                process_name = "unknown"
                process_username = "unknown"
                process_cmdline = []
                process_create_time = None
                process_exe = None
            
            # Prepare the result with detailed information
            result = {
                "pid": pid,
                "name": process_name,
                "user": process_username,
                "forced": force,
                "cmd": process_cmdline,
                "exe": process_exe,
                "create_time": process_create_time,
                "os_type": platform.system().lower(),
                "success": True
            }
            
            # Get process memory and CPU usage if available
            try:
                memory_info = process.memory_info()
                result["memory_usage"] = {
                    "rss": memory_info.rss,
                    "rss_readable": self._format_bytes(memory_info.rss)
                }
                result["cpu_percent"] = process.cpu_percent(interval=0.1)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                # Process might have already terminated or we don't have permission
                pass
            
            # Terminate the process
            if force:
                process.kill()  # SIGKILL
                action = "force terminated"
                result["signal"] = "SIGKILL"
            else:
                process.terminate()  # SIGTERM
                action = "terminated"
                result["signal"] = "SIGTERM"
            
            # Create detailed message
            message = f"Process {pid} ({process_name}) was {action} successfully"
            
            # Add user info
            if process_username and process_username != "unknown":
                message += f", owned by user '{process_username}'"
            
            # Add command line info if available
            if process_cmdline:
                cmd_str = " ".join(process_cmdline)
                if len(cmd_str) > 50:
                    cmd_str = cmd_str[:47] + "..."
                message += f". Command: {cmd_str}"
            
            result["message"] = message
            
            return result
        except psutil.NoSuchProcess:
            return {
                "success": False,
                "error": f"Process {pid} not found",
                "message": f"Failed to terminate process: PID {pid} not found or has already terminated"
            }
        except psutil.AccessDenied:
            return {
                "success": False,
                "error": f"Access denied when trying to terminate process {pid}. Try with administrator privileges.",
                "message": f"Failed to terminate process {pid}: Access denied. This process may require elevated privileges to terminate."
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error terminating process: {str(e)}",
                "message": f"Failed to terminate process {pid}: {str(e)}"
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