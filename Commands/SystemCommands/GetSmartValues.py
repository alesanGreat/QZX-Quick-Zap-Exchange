#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
GetSmartValues Command - Retrieves disk information using S.M.A.R.T. technology
"""

import os
import platform
import subprocess
import json
from Core.command_base import CommandBase

class GetSmartValuesCommand(CommandBase):
    """
    Command to retrieve S.M.A.R.T. disk information and health status
    """
    
    name = "getSmartValues"
    description = "Retrieves disk health information using S.M.A.R.T. technology"
    category = "system"
    
    parameters = [
        {
            'name': 'disk',
            'description': 'Disk identifier (e.g., "sda" on Linux, "PhysicalDrive0" on Windows)',
            'required': True
        },
        {
            'name': 'format',
            'description': 'Output format: "full" for all data, "health" for health summary',
            'required': False,
            'default': 'health'
        }
    ]
    
    examples = [
        {
            'command': 'qzx getSmartValues sda',
            'description': 'Get health information for /dev/sda (Linux)'
        },
        {
            'command': 'qzx getSmartValues PhysicalDrive0 full',
            'description': 'Get full S.M.A.R.T. data for PhysicalDrive0 (Windows)'
        }
    ]
    
    def execute(self, disk, format='health'):
        """
        Retrieves S.M.A.R.T. disk information
        
        Args:
            disk (str): Disk identifier
            format (str, optional): Output format ("full" or "health")
            
        Returns:
            Operation result with S.M.A.R.T. information
        """
        try:
            # Check if format is valid
            if format not in ['full', 'health']:
                return {
                    "success": False,
                    "error": f"Invalid format '{format}'. Must be 'full' or 'health'."
                }
            
            # Check operating system
            system = platform.system().lower()
            
            # Initialize result
            result = {
                "disk": disk,
                "format": format,
                "success": True
            }
            
            # Execute based on platform
            if system == 'linux':
                if format == 'health':
                    cmd = ['smartctl', '-H', f'/dev/{disk}']
                else:
                    cmd = ['smartctl', '-a', '-j', f'/dev/{disk}']
            elif system == 'windows':
                if format == 'health':
                    cmd = ['smartctl', '-H', f'\\\\.\\{disk}']
                else:
                    cmd = ['smartctl', '-a', '-j', f'\\\\.\\{disk}']
            else:
                return {
                    "success": False,
                    "error": f"Unsupported operating system: {system}. This command currently supports Linux and Windows."
                }
            
            # Check if smartmontools (smartctl) is installed
            try:
                # Execute the command
                process = subprocess.run(
                    cmd, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False
                )
                
                # Check if the command executed successfully
                if process.returncode == 0 or process.returncode == 2:  # 2 means command executed but has issues
                    if format == 'full' and '-j' in cmd:
                        # Parse JSON output if format is full and JSON output was requested
                        try:
                            smart_data = json.loads(process.stdout)
                            result.update({
                                "smart_data": smart_data,
                                "message": "Successfully retrieved full S.M.A.R.T. data"
                            })
                        except json.JSONDecodeError:
                            # If JSON parsing fails, return raw output
                            result.update({
                                "output": process.stdout,
                                "message": "Retrieved S.M.A.R.T. data (raw format)"
                            })
                    else:
                        # Return raw output for health check or if JSON parsing wasn't enabled
                        result.update({
                            "output": process.stdout,
                            "message": "Retrieved S.M.A.R.T. health information"
                        })
                        
                        # Try to determine overall health status from output
                        if "PASSED" in process.stdout:
                            result["health_status"] = "PASSED"
                        elif "FAILED" in process.stdout:
                            result["health_status"] = "FAILED"
                        else:
                            result["health_status"] = "UNKNOWN"
                else:
                    return {
                        "success": False,
                        "error": f"smartctl failed with return code {process.returncode}",
                        "stderr": process.stderr
                    }
            except FileNotFoundError:
                return {
                    "success": False,
                    "error": "smartctl command not found. Please install smartmontools package."
                }
            
            return result
        except Exception as e:
            return {
                "success": False,
                "disk": disk,
                "error": str(e)
            } 