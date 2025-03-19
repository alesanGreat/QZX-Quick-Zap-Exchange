#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ListProcesses Command - Lists running processes
"""

import platform
from Core.command_base import CommandBase

class ListProcessesCommand(CommandBase):
    """
    Command to list running processes
    """
    
    name = "listProcesses"
    description = "Lists running processes (similar to 'ps' in Unix)"
    category = "system"
    
    parameters = [
        {
            'name': 'filter_str',
            'description': 'Optional string to filter process names',
            'required': False,
            'default': None
        },
        {
            'name': 'sort_by',
            'description': 'Field to sort results by (pid, cpu, memory, name)',
            'required': False,
            'default': 'cpu'
        },
        {
            'name': 'limit',
            'description': 'Maximum number of processes to display',
            'required': False,
            'default': 0  # 0 means no limit
        }
    ]
    
    examples = [
        {
            'command': 'qzx listProcesses',
            'description': 'List all processes'
        },
        {
            'command': 'qzx listProcesses python',
            'description': 'List processes containing "python" in their name'
        },
        {
            'command': 'qzx listProcesses null memory 10',
            'description': 'List the top 10 processes by memory usage'
        }
    ]
    
    def execute(self, filter_str=None, sort_by='cpu', limit=0):
        """
        Lists running processes
        
        Args:
            filter_str (str, optional): Optional string to filter process names
            sort_by (str, optional): Field to sort results by (pid, cpu, memory, name)
            limit (int, optional): Maximum number of processes to display
            
        Returns:
            Dictionary with the process list and operation status
        """
        # Import psutil here to avoid errors during module loading if not installed
        try:
            import psutil
        except ImportError:
            return {
                "success": False,
                "error": "The psutil module is required for this command. Install it with: pip install psutil",
                "message": "Failed to list processes: psutil module is not installed. Please install it with: pip install psutil"
            }
        
        try:
            # Convert limit to integer if not None
            if limit is not None and limit != "null":
                try:
                    limit = int(limit)
                except ValueError:
                    return {
                        "success": False,
                        "error": f"limit must be an integer, received '{limit}'",
                        "message": f"Error: The 'limit' parameter must be an integer, but received '{limit}'"
                    }
            elif limit == "null":
                limit = 0
            
            # If filter_str is "null", convert to None
            if filter_str == "null":
                filter_str = None
            
            # Validate sort_by
            valid_sort_fields = ['pid', 'cpu', 'memory', 'name']
            if sort_by not in valid_sort_fields:
                return {
                    "success": False,
                    "error": f"sort_by must be one of {valid_sort_fields}, received '{sort_by}'",
                    "message": f"Error: The 'sort_by' parameter must be one of these values: {', '.join(valid_sort_fields)}, but received '{sort_by}'"
                }
            
            # Map sort_by to the actual key in process information
            sort_key_map = {
                'pid': lambda p: p['pid'],
                'cpu': lambda p: p['cpu_percent'] or 0,
                'memory': lambda p: p['memory_percent'] or 0,
                'name': lambda p: p['name'].lower() if p['name'] else ''
            }
            
            # Prepare the result
            result = {
                "filter": filter_str,
                "sort_by": sort_by,
                "limit": limit if limit > 0 else None,
                "os_type": platform.system().lower(),
                "processes": [],
                "total_processes": 0,
                "displayed_processes": 0,
                "success": True
            }
            
            # Get process information
            processes = []
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'username', 'status']):
                try:
                    # Get process information
                    proc_info = proc.info
                    
                    # Skip processes without names
                    if not proc_info['name']:
                        continue
                    
                    # Apply filter if specified
                    if filter_str and filter_str.lower() not in proc_info['name'].lower():
                        continue
                    
                    # Add additional information
                    process_data = {
                        "pid": proc_info['pid'],
                        "name": proc_info['name'],
                        "cpu_percent": proc_info['cpu_percent'] or 0.0,
                        "memory_percent": proc_info['memory_percent'] or 0.0,
                        "username": proc_info['username'],
                        "status": proc_info['status']
                    }
                    
                    # Try to get additional information
                    try:
                        process_data["num_threads"] = proc.num_threads()
                        process_data["create_time"] = proc.create_time()
                        
                        # Get detailed memory usage
                        mem_info = proc.memory_info()
                        process_data["memory_rss"] = mem_info.rss
                        process_data["memory_rss_readable"] = self._format_bytes(mem_info.rss)
                        
                        # Get executable path if available
                        try:
                            process_data["exe"] = proc.exe()
                        except (psutil.AccessDenied, psutil.ZombieProcess):
                            pass
                    except (psutil.AccessDenied, psutil.ZombieProcess):
                        pass
                    
                    processes.append(process_data)
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
            
            # Sort processes according to the specified criteria
            processes.sort(key=sort_key_map[sort_by], reverse=(sort_by in ['cpu', 'memory']))
            
            # Limit results if requested
            total_processes = len(processes)
            if limit > 0:
                processes = processes[:limit]
            
            result["processes"] = processes
            result["total_processes"] = total_processes
            result["displayed_processes"] = len(processes)
            
            # Create a detailed message for the result
            filter_msg = f" containing '{filter_str}'" if filter_str else ""
            limit_msg = f", showing top {limit}" if limit > 0 else ""
            sort_msg = f", sorted by {sort_by}"
            
            # Calculate CPU and memory usage statistics for the message
            if processes:
                top_cpu_process = max(processes, key=lambda p: p["cpu_percent"])
                top_memory_process = max(processes, key=lambda p: p["memory_percent"])
                
                # Add statistics to the result
                result["stats"] = {
                    "top_cpu_process": {
                        "pid": top_cpu_process["pid"],
                        "name": top_cpu_process["name"],
                        "cpu_percent": top_cpu_process["cpu_percent"]
                    },
                    "top_memory_process": {
                        "pid": top_memory_process["pid"],
                        "name": top_memory_process["name"],
                        "memory_percent": top_memory_process["memory_percent"],
                        "memory_rss_readable": top_memory_process.get("memory_rss_readable", "N/A")
                    }
                }
                
                # Add details about top processes to our message
                top_proc_msg = (
                    f"Highest CPU process: {top_cpu_process['name']} (PID {top_cpu_process['pid']}, {top_cpu_process['cpu_percent']:.1f}% CPU). "
                    f"Highest memory process: {top_memory_process['name']} (PID {top_memory_process['pid']}, "
                    f"{top_memory_process['memory_percent']:.1f}% memory, {top_memory_process.get('memory_rss_readable', 'N/A')})."
                )
            else:
                top_proc_msg = "No processes found matching the specified criteria."
            
            # Main message with all information
            message = (
                f"Found {total_processes} processes{filter_msg}{sort_msg}{limit_msg}. "
                f"Displaying {result['displayed_processes']} result(s). "
            )
            
            # Add top processes information if processes exist
            if processes:
                message += top_proc_msg
            
            # Add the message to the result
            result["message"] = message
            
            return result
        except Exception as e:
            return {
                "success": False,
                "error": f"Error listing processes: {str(e)}",
                "message": f"Failed to list processes: {str(e)}"
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