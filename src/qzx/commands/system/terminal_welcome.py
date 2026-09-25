#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
TerminalWelcome Module - Manages the welcome screen for QZX Terminal
"""

import importlib

from qzx.commands.system._terminal_welcome_details import (
    collect_system_info,
    format_gpu_result,
)
from qzx.welcome_text import WELCOME_BORDER, basic_welcome_message

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
        interactive=False,
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
            interactive (bool): Whether the text is displayed inside the QZX
                interactive terminal rather than by a one-shot shell command.
        """
        if qzx_version is None:
            from qzx import __version__

            qzx_version = __version__
        self.qzx_version = qzx_version
        self._system_info = None
        self._system_info_provider = system_info_provider
        self._psutil_loader = psutil_loader or _load_psutil
        self._psutil_module = _PSUTIL_UNSET
        self.interactive = bool(interactive)

    @property
    def system_info(self):
        """Collect expensive environment details only when a caller needs them."""
        if self._system_info is None:
            provider = self._system_info_provider or self._get_system_info
            self._system_info = provider()
        return self._system_info

    def _optional_psutil(self):
        """Resolve the optional dependency at most once per presentation."""
        if self._psutil_module is _PSUTIL_UNSET:
            self._psutil_module = self._psutil_loader()
        return self._psutil_module
    
    def get_welcome_message(self, show_full_info=False):
        """
        Generate the welcome message
        
        Args:
            show_full_info (bool): Whether to show full system information
            
        Returns:
            str: Formatted welcome message
        """
        welcome = basic_welcome_message(
            self.qzx_version,
            interactive=self.interactive,
        )
        if not show_full_info:
            return welcome

        lines = welcome.rstrip("\n").splitlines()
        if lines and lines[-1] == WELCOME_BORDER:
            lines.pop()
        basic_message = "\n".join(lines)
        return (
            f"{basic_message}\n\n"
            "DETAILED SYSTEM SNAPSHOT (explicitly requested)\n"
            "=================================================\n\n"
            "System\n"
            "------\n"
            f"{self._format_system_info()}\n\n"
            "Memory\n"
            "------\n"
            f"{self._format_ram_info()}\n\n"
            "Storage\n"
            "-------\n"
            f"{self._format_disk_info()}\n"
            f"{WELCOME_BORDER}\n"
        )
    
    def _get_system_info(self):
        """Collect the detailed system snapshot on explicit demand."""
        return collect_system_info(self._optional_psutil())

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

        if "ram_total" not in info:
            if self._optional_psutil() is None:
                return "RAM information not available (requires 'psutil' module)"
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

        if "disk_info" not in info or not info["disk_info"]:
            if self._optional_psutil() is None:
                return "Disk information not available (requires 'psutil' module)"
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
        """Get and format GPU information when explicitly requested."""
        try:
            from qzx.commands.system.get_gpu_info import GetGpuInfoCommand

            gpu_result = GetGpuInfoCommand().execute(detailed=True)
            return format_gpu_result(gpu_result)
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
