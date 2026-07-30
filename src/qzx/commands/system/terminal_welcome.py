#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
TerminalWelcome Module - Manages the welcome screen for QZX Terminal
"""

import importlib
import platform

from qzx.welcome_text import basic_welcome_message

_PSUTIL_UNSET = object()
_PSUTIL_MODULE = _PSUTIL_UNSET


def _load_psutil():
    """Load optional probes only for an explicitly detailed request."""
    global _PSUTIL_MODULE
    if _PSUTIL_MODULE is _PSUTIL_UNSET:
        try:
            _PSUTIL_MODULE = importlib.import_module("psutil")
        except ImportError:
            _PSUTIL_MODULE = None
    return _PSUTIL_MODULE


class TerminalWelcome:
    """
    Class that manages the QZX Terminal welcome screen
    """
    
    def __init__(
        self,
        qzx_version=None,
        system_info_provider=None,
        psutil_loader=None,
    ):
        """
        Initialize the welcome manager
        
        Args:
            qzx_version (str): Current QZX version. Defaults to the packaged
                development version.
            system_info_provider (callable): Optional deterministic provider
                for the detailed view.
            psutil_loader (callable): Optional dependency loader used only by
                the detailed view.
        """
        if qzx_version is None:
            from qzx import __version__

            qzx_version = __version__
        self.qzx_version = qzx_version
        self._system_info = None
        self._system_info_provider = system_info_provider
        self._psutil_loader = psutil_loader or _load_psutil

    @property
    def system_info(self):
        """Collect expensive environment details only when a caller needs them."""
        if self._system_info is None:
            provider = self._system_info_provider or self._get_system_info
            self._system_info = provider()
        return self._system_info
    
    def get_welcome_message(self, show_full_info=False):
        """
        Generate the welcome message
        
        Args:
            show_full_info (bool): Whether to show full system information
            
        Returns:
            str: Formatted welcome message
        """
        welcome = basic_welcome_message(self.qzx_version)
        if show_full_info:
            welcome += """
System
------
{}

Memory
------
{}

Storage
-------
{}
=================================================================
""".format(
                self._format_system_info(),
                self._format_ram_info(),
                self._format_disk_info(),
            )
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
        
        # Disk probes can block on sleeping or disconnected mount points, so
        # even importing the optional dependency belongs to the detailed path.
        psutil_module = self._psutil_loader()
        if psutil_module is not None:
            # RAM
            try:
                virtual_memory = psutil_module.virtual_memory()
                info["ram_total"] = virtual_memory.total
                info["ram_available"] = virtual_memory.available
                info["ram_used"] = virtual_memory.used
                info["ram_percent"] = virtual_memory.percent
            except Exception:
                pass
            
            # Disk
            try:
                disk_info = []
                for partition in psutil_module.disk_partitions(all=False):
                    try:
                        usage = psutil_module.disk_usage(partition.mountpoint)
                        disk_info.append({
                            "device": partition.device,
                            "mountpoint": partition.mountpoint,
                            "fstype": partition.fstype,
                            "total": usage.total,
                            "used": usage.used,
                            "free": usage.free,
                            "percent": usage.percent
                        })
                    except Exception:
                        pass
                info["disk_info"] = disk_info
            except Exception:
                pass
            
            # CPU
            try:
                info["cpu_count_physical"] = psutil_module.cpu_count(logical=False)
                info["cpu_count_logical"] = psutil_module.cpu_count(logical=True)
            except Exception:
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
        
        if self._psutil_loader() is None:
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
        
        if self._psutil_loader() is None:
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
            disk_line = "{} ({}): ".format(
                disk.get("device", "Unknown"),
                disk.get("mountpoint", ""),
            )
            disk_line += (
                f"Total: {total} | Used: {used} ({percent}%) | Free: {free}"
            )
            
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
        # Keep GPU probing optional because it may invoke platform utilities.
        try:
            from qzx.commands.system.get_gpu_info import GetGpuInfoCommand
            
            gpu_result = GetGpuInfoCommand().execute(detailed=True)
            
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
                    if "total_mib" in memory:
                        total = memory["total_mib"]
                        used = memory.get("used_mib")
                        gpu_line += (
                            f" | Memory: {used}/{total} MiB"
                            if used is not None
                            else f" | Memory: {total} MiB"
                        )
                    elif "total_readable" in memory:
                        gpu_line += (
                            f" | Memory: {memory['total_readable']}"
                        )
                    elif "reported" in memory:
                        gpu_line += f" | Memory: {memory['reported']}"
                
                # Temperature and utilization if available
                if "temperature_celsius" in gpu:
                    gpu_line += (
                        f" | Temp: {gpu['temperature_celsius']} °C"
                    )
                
                if "utilization_percent" in gpu:
                    gpu_line += (
                        f" | Usage: {gpu['utilization_percent']}%"
                    )
                
                if result:
                    result += "\n"
                result += gpu_line
            
            return result
        except Exception:
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
        except (TypeError, ValueError, OverflowError):
            return str(bytes_val)
