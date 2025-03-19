#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
GetRAMInfo Command - Retrieves information about system RAM
"""

import psutil
from Core.command_base import CommandBase

class GetRAMInfoCommand(CommandBase):
    """
    Command to get information about system RAM
    """
    
    name = "getRAMInfo"
    description = "Gets detailed information about system RAM usage"
    category = "system"
    
    parameters = []
    
    examples = [
        {
            'command': 'qzx getRAMInfo',
            'description': 'Get detailed information about system memory usage'
        }
    ]
    
    def execute(self):
        """
        Gets information about system RAM
        
        Returns:
            Dictionary with RAM information
        """
        try:
            # Get memory information
            virtual_memory = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            # Prepare the output
            ram_info = {
                "virtual_memory": {
                    "total": virtual_memory.total,
                    "total_readable": self._format_bytes(virtual_memory.total),
                    "available": virtual_memory.available,
                    "available_readable": self._format_bytes(virtual_memory.available),
                    "used": virtual_memory.used,
                    "used_readable": self._format_bytes(virtual_memory.used),
                    "free": virtual_memory.free,
                    "free_readable": self._format_bytes(virtual_memory.free),
                    "percent": virtual_memory.percent
                },
                "swap": {
                    "total": swap.total,
                    "total_readable": self._format_bytes(swap.total),
                    "used": swap.used,
                    "used_readable": self._format_bytes(swap.used),
                    "free": swap.free,
                    "free_readable": self._format_bytes(swap.free),
                    "percent": swap.percent
                }
            }
            
            # Try to get additional memory information where available
            try:
                # Add memory by type if available
                ram_info["memory_stats"] = {}
                
                # Add active/inactive memory if available
                if hasattr(virtual_memory, 'active'):
                    ram_info["memory_stats"]["active"] = {
                        "value": virtual_memory.active,
                        "readable": self._format_bytes(virtual_memory.active)
                    }
                
                if hasattr(virtual_memory, 'inactive'):
                    ram_info["memory_stats"]["inactive"] = {
                        "value": virtual_memory.inactive,
                        "readable": self._format_bytes(virtual_memory.inactive)
                    }
                
                if hasattr(virtual_memory, 'buffers'):
                    ram_info["memory_stats"]["buffers"] = {
                        "value": virtual_memory.buffers,
                        "readable": self._format_bytes(virtual_memory.buffers)
                    }
                
                if hasattr(virtual_memory, 'cached'):
                    ram_info["memory_stats"]["cached"] = {
                        "value": virtual_memory.cached,
                        "readable": self._format_bytes(virtual_memory.cached)
                    }
                
                if hasattr(virtual_memory, 'shared'):
                    ram_info["memory_stats"]["shared"] = {
                        "value": virtual_memory.shared,
                        "readable": self._format_bytes(virtual_memory.shared)
                    }
                
                if hasattr(virtual_memory, 'slab'):
                    ram_info["memory_stats"]["slab"] = {
                        "value": virtual_memory.slab,
                        "readable": self._format_bytes(virtual_memory.slab)
                    }
            except:
                pass  # Ignore if additional stats are not available
            
            # Try to get swap details
            try:
                if hasattr(swap, 'sin') and hasattr(swap, 'sout'):
                    ram_info["swap"]["sin"] = swap.sin
                    ram_info["swap"]["sout"] = swap.sout
            except:
                pass  # Ignore if swap details are not available
            
            # Create a detailed message for verbose output
            vm = ram_info["virtual_memory"]
            sw = ram_info["swap"]
            
            # Calculate used percentage (rounded to 1 decimal place)
            ram_used_percent = round(vm["percent"], 1)
            swap_used_percent = round(sw["percent"], 1)
            
            # Format a comprehensive message about memory usage
            message = (
                f"RAM usage: {vm['used_readable']} of {vm['total_readable']} "
                f"({ram_used_percent}%) used, {vm['available_readable']} available. "
            )
            
            # Add swap info if swap is enabled (total > 0)
            if sw["total"] > 0:
                message += (
                    f"Swap: {sw['used_readable']} of {sw['total_readable']} "
                    f"({swap_used_percent}%) used, {sw['free_readable']} free."
                )
            else:
                message += "No swap space configured."
            
            # Add additional memory details if available
            if "memory_stats" in ram_info:
                stats = ram_info["memory_stats"]
                if "cached" in stats:
                    message += f" Cached memory: {stats['cached']['readable']}."
                if "buffers" in stats:
                    message += f" Buffers: {stats['buffers']['readable']}."
            
            # Return with success flag and verbose message
            result = {
                "success": True,
                "message": message,
                "ram_info": ram_info
            }
            
            return result
        except Exception as e:
            return {
                "success": False,
                "error": f"Error getting RAM information: {str(e)}",
                "message": f"Failed to retrieve system memory information: {str(e)}"
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