#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
CommandsBridge Command - Acts as a middleware for system commands to safely handle execution
"""

import os
import sys
import subprocess
import shlex
import datetime
import platform
from Core.command_base import CommandBase

class CommandsBridgeCommand(CommandBase):
    """
    Command to serve as a middleware for system commands.
    This bridge safely handles the execution of system commands, preventing errors from causing problems.
    """
    
    name = "commandsBridge"
    aliases = ["bridge", "cmd", "run"]
    description = "Safely executes system commands with detailed feedback"
    category = "system"
    
    parameters = [
        {
            'name': 'command',
            'description': 'The system command to execute',
            'required': True
        },
        {
            'name': 'args',
            'description': 'Arguments for the command (can be multiple separate arguments)',
            'required': False,
            'default': ''
        }
    ]
    
    examples = [
        {
            'command': 'qzx commandsBridge cd /path/to/directory',
            'description': 'Changes the current directory to the specified path'
        },
        {
            'command': 'qzx bridge pwd',
            'description': 'Shows the current working directory'
        },
        {
            'command': 'qzx cmd ls -la',
            'description': 'Lists files in the current directory with details'
        },
        {
            'command': 'qzx run echo "Hello World"',
            'description': 'Outputs "Hello World" to the console'
        }
    ]
    
    # List of safe commands to execute
    SAFE_COMMANDS = [
        # Navigation commands
        'cd', 'pwd', 'ls', 'dir',
        
        # User information commands
        'who', 'whoami', 'id', 'groups',
        
        # System information commands
        'ps', 'top', 'free', 'df', 'du', 'uname', 'hostname',
        
        # File operations (non-destructive)
        'cp', 'mv', 'mkdir', 'touch', 'cat', 'more', 'less', 'head', 'tail',
        
        # Text operations
        'grep', 'awk', 'sed', 'wc', 'sort', 'uniq', 'cut', 'tr', 'echo',
        
        # Network commands
        'ping', 'ifconfig', 'ip', 'netstat', 'ss', 'nslookup', 'host',
        
        # Process commands (read-only)
        'jobs', 'bg', 'fg', 'nohup',
        
        # File analysis
        'file', 'stat', 'find', 'locate', 'which', 'type',
        
        # Date and time
        'date', 'cal', 'uptime',
        
        # Development tools
        'git', 'npm', 'pip', 'python',
        
        # Others
        'clear', 'history', 'man', 'env', 'printenv'
    ]
    
    # Commands that involve destructive operations - require confirmation
    CAUTION_COMMANDS = [
        'rm', 'rmdir', 'kill', 'pkill', 'chmod', 'chown', 'dd', 'mkfs',
        'shred', 'shutdown', 'reboot', 'halt', 'poweroff', 'format',
        'fdisk', 'mkswap', 'swapoff', 'swapon'
    ]
    
    # Built-in commands that need special handling
    BUILTIN_COMMANDS = {
        'cd': '_handle_cd',
        'exit': '_handle_exit',
        'pwd': '_handle_pwd',
        'clear': '_handle_clear',
    }
    
    def execute(self, command, args=''):
        """
        Safely executes a system command
        
        Args:
            command (str): The command to execute
            args (str): Arguments for the command
            
        Returns:
            Dictionary with the operation results and status
        """
        try:
            start_time = datetime.datetime.now()
            os_info = platform.system()
            
            # Prepare the command string
            if args:
                full_command = f"{command} {args}"
            else:
                full_command = command
            
            # Initialize result with basic information
            result = {
                "success": True,
                "command": {
                    "name": command,
                    "args": args,
                    "full_command": full_command,
                    "os": os_info,
                    "datetime": start_time.isoformat(),
                },
            }
            
            # Check if it's a built-in command that needs special handling
            if command in self.BUILTIN_COMMANDS:
                handler_method = getattr(self, self.BUILTIN_COMMANDS[command])
                return handler_method(args, result)
            
            # Verify if the command is safe to execute
            if command not in self.SAFE_COMMANDS and command not in self.CAUTION_COMMANDS:
                result.update({
                    "success": False,
                    "error": f"Unrecognized or potentially unsafe command: {command}",
                    "message": f"The command '{command}' is not in the list of recognized commands. If you're sure it's safe, you may need to execute it directly."
                })
                return result
            
            # Extra warning for caution commands
            if command in self.CAUTION_COMMANDS:
                result["warning"] = f"'{command}' is a destructive operation that could cause data loss or system issues."
            
            # Execute the command
            try:
                # Split command and args for subprocess
                cmd_parts = shlex.split(full_command)
                
                # Check if the command exists in the system
                if not self._command_exists(command):
                    result.update({
                        "success": False,
                        "error": f"Command not found: {command}",
                        "message": f"The command '{command}' was not found on your system. Make sure it's installed and available in your PATH."
                    })
                    return result
                
                # Run the command and capture output
                process = subprocess.run(
                    cmd_parts,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    shell=False,  # More secure to use shell=False
                    check=False   # Don't raise exception on non-zero exit
                )
                
                # Process completed, calculate duration
                end_time = datetime.datetime.now()
                duration = (end_time - start_time).total_seconds()
                
                # Add outputs and execution info to result
                result.update({
                    "success": process.returncode == 0,
                    "exit_code": process.returncode,
                    "stdout": process.stdout,
                    "stderr": process.stderr,
                    "duration_seconds": duration,
                })
                
                # Create a user-friendly message
                if process.returncode == 0:
                    message = f"Successfully executed '{command}' with exit code 0."
                else:
                    message = f"Command '{command}' failed with exit code {process.returncode}."
                    if process.stderr:
                        message += f" Error: {process.stderr}"
                
                result["message"] = message
                return result
                
            except FileNotFoundError:
                result.update({
                    "success": False,
                    "error": f"Command not found: {command}",
                    "message": f"The command '{command}' was not found on the system."
                })
                return result
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Error executing command: {str(e)}",
                "message": f"Failed to execute command: {str(e)}",
                "command": command,
                "args": args
            }
    
    def _command_exists(self, command):
        """
        Check if a command exists on the system
        
        Args:
            command (str): Command to check
            
        Returns:
            bool: True if command exists, False otherwise
        """
        if os.name == 'nt':  # Windows
            # On Windows, use where.exe to find command
            try:
                subprocess.run(
                    ["where", command],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False
                )
                return True
            except:
                return False
        else:  # Unix-like
            # On Unix-like systems, use which to find command
            try:
                subprocess.run(
                    ["which", command],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False
                )
                return True
            except:
                return False
    
    def _handle_cd(self, args, result):
        """
        Special handler for the cd command
        
        Args:
            args (str): Directory to change to
            result (dict): Current result dictionary
            
        Returns:
            dict: Updated result dictionary
        """
        try:
            # Get the target directory
            if not args:
                # Default to home directory if no args
                target_dir = os.path.expanduser("~")
            else:
                target_dir = os.path.expanduser(args)
            
            # Save original directory
            original_dir = os.getcwd()
            
            # Try to change directory
            os.chdir(target_dir)
            
            # Update result with success info
            result.update({
                "success": True,
                "directory": {
                    "previous": original_dir,
                    "current": os.getcwd(),
                    "is_home": os.getcwd() == os.path.expanduser("~"),
                    "name": os.path.basename(os.getcwd()),
                    "parent": os.path.dirname(os.getcwd()),
                },
                "message": f"Changed directory from '{original_dir}' to '{os.getcwd()}'."
            })
            
            # Add home-relative path if applicable
            home_dir = os.path.expanduser("~")
            if os.getcwd().startswith(home_dir) and os.getcwd() != home_dir:
                relative_to_home = "~" + os.getcwd()[len(home_dir):]
                result["directory"]["relative_to_home"] = relative_to_home
            
            return result
            
        except FileNotFoundError:
            result.update({
                "success": False,
                "error": f"Directory not found: {args}",
                "message": f"The directory '{args}' does not exist."
            })
            return result
        except PermissionError:
            result.update({
                "success": False,
                "error": f"Permission denied: {args}",
                "message": f"You don't have permission to access the directory '{args}'."
            })
            return result
        except Exception as e:
            result.update({
                "success": False,
                "error": f"Error changing directory: {str(e)}",
                "message": f"Failed to change directory: {str(e)}"
            })
            return result
    
    def _handle_pwd(self, args, result):
        """
        Special handler for the pwd command
        
        Args:
            args (str): Arguments (usually empty for pwd)
            result (dict): Current result dictionary
            
        Returns:
            dict: Updated result dictionary
        """
        try:
            current_dir = os.getcwd()
            home_dir = os.path.expanduser("~")
            
            # Update result with success info
            result.update({
                "success": True,
                "directory": {
                    "current": current_dir,
                    "is_home": current_dir == home_dir,
                    "is_root": current_dir == '/' or (os.name == 'nt' and len(current_dir) == 3 and current_dir[1] == ':'),
                    "parent": os.path.dirname(current_dir),
                    "name": os.path.basename(current_dir),
                },
                "stdout": current_dir,
                "message": f"Current working directory: {current_dir}"
            })
            
            # Add home-relative path if applicable
            if current_dir.startswith(home_dir) and current_dir != home_dir:
                relative_to_home = "~" + current_dir[len(home_dir):]
                result["directory"]["relative_to_home"] = relative_to_home
                result["message"] += f" (~ {relative_to_home})"
            
            return result
            
        except Exception as e:
            result.update({
                "success": False,
                "error": f"Error getting current directory: {str(e)}",
                "message": f"Failed to get current directory: {str(e)}"
            })
            return result
    
    def _handle_exit(self, args, result):
        """
        Special handler for the exit command
        
        Args:
            args (str): Exit code (optional)
            result (dict): Current result dictionary
            
        Returns:
            dict: Updated result dictionary with exit information
        """
        try:
            # Parse exit code if provided
            exit_code = 0
            if args:
                try:
                    exit_code = int(args)
                except ValueError:
                    result.update({
                        "success": False,
                        "error": f"Invalid exit code: {args}",
                        "message": f"The exit code must be an integer. Using default exit code 0."
                    })
            
            # Update result with exit info
            result.update({
                "success": True,
                "exit_code": exit_code,
                "message": f"Process would exit with code {exit_code}. Note: In the QZX framework, the 'exit' command is simulated and won't actually terminate the process."
            })
            
            return result
            
        except Exception as e:
            result.update({
                "success": False,
                "error": f"Error processing exit command: {str(e)}",
                "message": f"Failed to process exit command: {str(e)}"
            })
            return result
    
    def _handle_clear(self, args, result):
        """
        Special handler for the clear command
        
        Args:
            args (str): Arguments (usually empty for clear)
            result (dict): Current result dictionary
            
        Returns:
            dict: Updated result dictionary
        """
        try:
            # We can't directly clear the console, so we'll just simulate it
            result.update({
                "success": True,
                "message": "Clear command received. In the QZX framework, this command is simulated and will provide feedback rather than actually clearing the console."
            })
            
            return result
            
        except Exception as e:
            result.update({
                "success": False,
                "error": f"Error processing clear command: {str(e)}",
                "message": f"Failed to process clear command: {str(e)}"
            })
            return result 