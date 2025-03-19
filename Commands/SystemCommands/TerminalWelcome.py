#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
TerminalWelcome Module - Manages the welcome screen for QZX Terminal
"""

import os
import sys
import platform

# Try to import optional modules
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

class TerminalWelcome:
    """
    Class that manages the QZX Terminal welcome screen
    """
    
    def __init__(self, qzx_version="0.02"):
        """
        Initialize the welcome manager
        
        Args:
            qzx_version (str): Current QZX version
        """
        self.qzx_version = qzx_version
        self.system_info = self._get_system_info()
    
    def get_welcome_message(self, show_full_info=True):
        """
        Generate the welcome message
        
        Args:
            show_full_info (bool): Whether to show full system information
            
        Returns:
            str: Formatted welcome message
        """
        # Base message with enhanced professor greeting and version info
        welcome = f"""
=================================================================
Welcome Professor! 

QZX - Quick Zap Exchange - Version {self.qzx_version}
I am at your service. Ready to assist with your tasks.
=================================================================
"""

        # Basic instructions
        welcome += """
-----------------------------------------------------------------
Type 'list' to see available commands
Type 'help <command>' to get help on a specific command
Type 'WonderMyEnvironment' to see system information
Type 'exit' or press Ctrl+D to exit
=================================================================
"""
        return welcome
    
    def _get_system_info(self):
        """
        Get system information
        
        Returns:
            dict: System information
        """
        info = {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "architecture": platform.machine(),
            "processor": platform.processor(),
            "python_version": platform.python_version(),
            "python_implementation": platform.python_implementation()
        }
        
        # Additional information if psutil is available
        if PSUTIL_AVAILABLE:
            # RAM
            try:
                virtual_memory = psutil.virtual_memory()
                info["ram_total"] = virtual_memory.total
                info["ram_available"] = virtual_memory.available
                info["ram_used"] = virtual_memory.used
                info["ram_percent"] = virtual_memory.percent
            except:
                pass
            
            # Disk
            try:
                disk_info = []
                for partition in psutil.disk_partitions(all=False):
                    try:
                        usage = psutil.disk_usage(partition.mountpoint)
                        disk_info.append({
                            "device": partition.device,
                            "mountpoint": partition.mountpoint,
                            "fstype": partition.fstype,
                            "total": usage.total,
                            "used": usage.used,
                            "free": usage.free,
                            "percent": usage.percent
                        })
                    except:
                        pass
                info["disk_info"] = disk_info
            except:
                pass
            
            # CPU
            try:
                info["cpu_count_physical"] = psutil.cpu_count(logical=False)
                info["cpu_count_logical"] = psutil.cpu_count(logical=True)
            except:
                pass
        
        return info
    
    def _format_system_info(self):
        """
        Format system information for display
        
        Returns:
            str: Formatted system information
        """
        info = self.system_info
        
        result = (
            f"Operating System: {info.get('system', 'Unknown')} {info.get('release', '')}\n"
            f"Version: {info.get('version', 'Unknown')}\n"
            f"Architecture: {info.get('architecture', 'Unknown')}\n"
        )
        
        if "processor" in info and info["processor"]:
            result += f"Processor: {info.get('processor')}\n"
        
        if PSUTIL_AVAILABLE:
            if "cpu_count_physical" in info:
                result += f"Physical cores: {info.get('cpu_count_physical', 'Unknown')}\n"
            if "cpu_count_logical" in info:
                result += f"Logical cores: {info.get('cpu_count_logical', 'Unknown')}\n"
        
        result += f"Python: {info.get('python_implementation', 'Unknown')} {info.get('python_version', '')}"
        
        return result
    
    def _format_ram_info(self):
        """
        Format RAM information for display
        
        Returns:
            str: Formatted RAM information
        """
        info = self.system_info
        
        if not PSUTIL_AVAILABLE:
            return "RAM information not available (requires 'psutil' module)"
        
        if "ram_total" not in info:
            return "RAM information not available"
        
        ram_total = self._format_bytes(info.get("ram_total", 0))
        ram_available = self._format_bytes(info.get("ram_available", 0))
        ram_used = self._format_bytes(info.get("ram_used", 0))
        ram_percent = info.get("ram_percent", 0)
        
        return f"Total: {ram_total} | Used: {ram_used} ({ram_percent}%) | Available: {ram_available}"
    
    def _format_disk_info(self):
        """
        Format disk information for display
        
        Returns:
            str: Formatted disk information
        """
        info = self.system_info
        
        if not PSUTIL_AVAILABLE:
            return "Disk information not available (requires 'psutil' module)"
        
        if "disk_info" not in info or not info["disk_info"]:
            return "Disk information not available"
        
        result = ""
        for disk in info["disk_info"]:
            total = self._format_bytes(disk.get("total", 0))
            used = self._format_bytes(disk.get("used", 0))
            free = self._format_bytes(disk.get("free", 0))
            percent = disk.get("percent", 0)
            
            # Format line for each disk
            disk_line = f"{disk.get('device', 'Unknown')} ({disk.get('mountpoint', '')}): "
            disk_line += f"Total: {total} | Used: {used} ({percent}%) | Free: {free}"
            
            if result:
                result += "\n"
            result += disk_line
        
        return result
    
    def _format_gpu_info(self):
        """
        Get and format information about GPUs
        
        Returns:
            str: Formatted GPU information, or None if not available
        """
        # Try to use GetGPULoad command if available
        try:
            # Import dynamically to avoid circular dependencies
            # This works because this module is not directly imported by GetGPULoad
            from Commands.SystemCommands.GetGPULoad import GetGPULoadCommand
            
            # Create instance and execute
            gpu_command = GetGPULoadCommand()
            gpu_result = gpu_command.execute(detailed="true")
            
            if not gpu_result or not isinstance(gpu_result, dict) or not gpu_result.get("success", False):
                return None
            
            gpus = gpu_result.get("gpus", [])
            if not gpus:
                return None
            
            # Format output
            result = ""
            for i, gpu in enumerate(gpus):
                name = gpu.get("name", "Unknown GPU")
                vendor = gpu.get("vendor", "")
                
                # Base line
                gpu_line = f"{i+1}. {name}"
                if vendor:
                    gpu_line += f" [{vendor}]"
                
                # Memory information if available
                memory = gpu.get("memory", {})
                if memory:
                    if "total" in memory and "used" in memory:
                        total = memory.get("total", "")
                        used = memory.get("used", "")
                        
                        # Format if numeric values
                        if isinstance(total, (int, float)) and isinstance(used, (int, float)):
                            total = self._format_bytes(total)
                            used = self._format_bytes(used)
                        
                        gpu_line += f" | Memory: {used}/{total}"
                    elif "total" in memory:
                        total = memory.get("total", "")
                        if isinstance(total, (int, float)):
                            total = self._format_bytes(total)
                        gpu_line += f" | Memory: {total}"
                
                # Temperature and utilization if available
                if "temperature" in gpu:
                    gpu_line += f" | Temp: {gpu['temperature']}"
                
                if "utilization" in gpu:
                    gpu_line += f" | Usage: {gpu['utilization']}"
                
                if result:
                    result += "\n"
                result += gpu_line
            
            return result
        except Exception as e:
            # If there's an error, simply return None
            print(f"Error getting GPU information: {e}")
            return None
    
    def _format_bytes(self, bytes_val):
        """
        Format a byte value to a readable string
        
        Args:
            bytes_val: Value in bytes
            
        Returns:
            str: Formatted string
        """
        try:
            bytes_val = float(bytes_val)
            for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
                if bytes_val < 1024.0:
                    return f"{bytes_val:.2f} {unit}"
                bytes_val /= 1024.0
            return f"{bytes_val:.2f} PB"
        except:
            return str(bytes_val) 