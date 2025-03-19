#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
RunScript Command - Executes a script with parameters
"""

import os
import sys
import subprocess
import platform
from Core.command_base import CommandBase

class RunScriptCommand(CommandBase):
    """
    Command to execute a script with parameters
    """
    
    name = "runScript"
    description = "Executes a script with parameters"
    category = "system"
    
    parameters = [
        {
            'name': 'script_path',
            'description': 'Path to the script to execute',
            'required': True
        },
        {
            'name': 'args',
            'description': 'Arguments to pass to the script',
            'required': False,
            'default': [],
            'is_variadic': True
        }
    ]
    
    examples = [
        {
            'command': 'qzx runScript myscript.py',
            'description': 'Execute a Python script'
        },
        {
            'command': 'qzx runScript myscript.py arg1 arg2',
            'description': 'Execute a Python script with arguments'
        },
        {
            'command': 'qzx runScript script.sh',
            'description': 'Execute a shell script'
        }
    ]
    
    def execute(self, script_path, *args):
        """
        Executes a script with parameters
        
        Args:
            script_path (str): Path to the script to execute
            *args: List of arguments to pass to the script
            
        Returns:
            Dictionary with the execution results and status
        """
        try:
            if not os.path.exists(script_path):
                return {
                    "success": False,
                    "error": f"Script '{script_path}' not found",
                    "message": f"Failed to execute script: File '{script_path}' does not exist",
                    "script": script_path,
                    "args": args
                }
            
            # Get script details
            script_name = os.path.basename(script_path)
            script_dir = os.path.dirname(os.path.abspath(script_path))
            script_size = os.path.getsize(script_path)
            script_type = os.path.splitext(script_path)[1].lower()
            
            # Determine how to execute the script based on its extension
            os_type = platform.system().lower()
            
            if script_path.endswith('.py'):
                cmd = [sys.executable, script_path] + list(args)
                script_type = "Python"
            elif script_path.endswith('.sh') and os_type != 'windows':
                cmd = ['bash', script_path] + list(args)
                script_type = "Bash"
            elif script_path.endswith('.bat') and os_type == 'windows':
                cmd = [script_path] + list(args)
                script_type = "Batch"
            else:
                return {
                    "success": False,
                    "error": f"Unsupported script type: {script_path}",
                    "message": f"Failed to execute script: Unsupported file type '{os.path.splitext(script_path)[1]}'",
                    "script": script_path,
                    "script_type": script_type,
                    "args": args
                }
            
            # Create message about script execution
            cmd_str = ' '.join(cmd)
            execution_msg = f"Executing {script_type} script '{script_name}'"
            if args:
                execution_msg += f" with arguments: {' '.join(str(arg) for arg in args)}"
            
            # Run the script with subprocess
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True,
                check=False
            )
            
            # Prepare output details
            stdout = result.stdout.strip() if result.stdout else ""
            stderr = result.stderr.strip() if result.stderr else ""
            success = result.returncode == 0
            
            # Create response message based on execution result
            if success:
                message = f"Successfully executed {script_type} script '{script_name}'"
                if result.returncode == 0 and stdout:
                    message += f" with {len(stdout.splitlines())} lines of output"
            else:
                message = f"Script '{script_name}' failed with exit code {result.returncode}"
                if stderr:
                    message += f" and produced error output"
            
            # Return detailed information about the execution
            return {
                "success": success,
                "message": message,
                "script": script_path,
                "script_info": {
                    "name": script_name,
                    "directory": script_dir,
                    "size_bytes": script_size,
                    "type": script_type
                },
                "args": args,
                "execution": {
                    "command": cmd_str,
                    "exit_code": result.returncode
                },
                "output": stdout,
                "error": stderr if not success else None,
                "summary": execution_msg
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error executing script: {str(e)}",
                "message": f"Failed to execute script '{script_path}': {str(e)}",
                "script": script_path,
                "args": args
            } 