#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
GetDiskInfo Command - Retrieves information about disk space usage
"""

import psutil
import os
from Core.command_base import CommandBase

class GetDiskInfoCommand(CommandBase):
    """
    Command to get information about disk space usage
    """
    
    name = "getDiskInfo"
    description = "Gets information about disk space usage"
    category = "system"
    
    parameters = [
        {
            'name': 'path',
            'description': 'Path to get disk information from. If not provided, all disks will be shown',
            'required': False,
            'default': None
        }
    ]
    
    examples = [
        {
            'command': 'qzx getDiskInfo',
            'description': 'Get information about all available disks'
        },
        {
            'command': 'qzx getDiskInfo C:',
            'description': 'Get information about the C: drive (Windows)'
        },
        {
            'command': 'qzx getDiskInfo /home',
            'description': 'Get information about the /home partition (Linux/Mac)'
        }
    ]
    
    def execute(self, path=None):
        """
        Gets disk space information for the specified path or all disks
        
        Args:
            path (str, optional): Path to get information from. If not provided, all disks will be shown.
            
        Returns:
            Dictionary with disk information and success status
        """
        try:
            if path:
                # Get information for a specific path
                if os.path.exists(path):
                    disk_usage = psutil.disk_usage(path)
                    
                    # Create disk info with raw values for additional processing
                    disk_info = {
                        'path': path,
                        'total_bytes': disk_usage.total,
                        'used_bytes': disk_usage.used,
                        'free_bytes': disk_usage.free,
                        'total': self._format_bytes(disk_usage.total),
                        'used': self._format_bytes(disk_usage.used),
                        'free': self._format_bytes(disk_usage.free),
                        'percent': disk_usage.percent
                    }
                    
                    # Create detailed message
                    message = (
                        f"Disk information for '{path}': "
                        f"{disk_info['used']} used of {disk_info['total']} total "
                        f"({disk_info['percent']}% used), "
                        f"{disk_info['free']} free."
                    )
                    
                    return {
                        'success': True,
                        'message': message,
                        'disk_info': disk_info
                    }
                else:
                    return {
                        'success': False,
                        'error': f"Path '{path}' does not exist",
                        'message': f"Failed to get disk information: Path '{path}' does not exist."
                    }
            else:
                # Get all disk partitions
                disks = []
                for partition in psutil.disk_partitions(all=False):
                    try:
                        usage = psutil.disk_usage(partition.mountpoint)
                        disks.append({
                            'device': partition.device,
                            'mountpoint': partition.mountpoint,
                            'fstype': partition.fstype,
                            'total_bytes': usage.total,
                            'used_bytes': usage.used,
                            'free_bytes': usage.free,
                            'total': self._format_bytes(usage.total),
                            'used': self._format_bytes(usage.used),
                            'free': self._format_bytes(usage.free),
                            'percent': usage.percent
                        })
                    except (PermissionError, OSError):
                        # Skip partitions that can't be accessed
                        continue
                
                # Calculate totals across all disks
                total_space = sum(disk['total_bytes'] for disk in disks)
                used_space = sum(disk['used_bytes'] for disk in disks)
                free_space = sum(disk['free_bytes'] for disk in disks)
                
                # Calculate overall usage percentage
                percent = 0
                if total_space > 0:
                    percent = round((used_space / total_space) * 100, 1)
                
                # Create summary message
                summary_message = (
                    f"Found {len(disks)} disk{'s' if len(disks) != 1 else ''}. "
                    f"Total storage: {self._format_bytes(total_space)}, "
                    f"Used: {self._format_bytes(used_space)} ({percent}%), "
                    f"Free: {self._format_bytes(free_space)}."
                )
                
                # Add message for each disk
                disk_details = []
                for disk in disks:
                    disk_details.append(
                        f"{disk['device']} ({disk['mountpoint']}): "
                        f"{disk['used']} used of {disk['total']} "
                        f"({disk['percent']}% used), {disk['free']} free."
                    )
                
                # Combine summary and details into a single message
                if disk_details:
                    disk_message = "\n".join(disk_details)
                    message = f"{summary_message}\n\nDisk details:\n{disk_message}"
                else:
                    message = summary_message
                
                return {
                    'success': True,
                    'message': message,
                    'summary': {
                        'total_disks': len(disks),
                        'total_space': total_space,
                        'total_space_readable': self._format_bytes(total_space),
                        'used_space': used_space,
                        'used_space_readable': self._format_bytes(used_space),
                        'free_space': free_space,
                        'free_space_readable': self._format_bytes(free_space),
                        'percent_used': percent
                    },
                    'disks': disks
                }
        except Exception as e:
            return {
                'success': False,
                'error': f"Error getting disk information: {str(e)}",
                'message': f"Failed to retrieve disk information: {str(e)}"
            }
    
    def _format_bytes(self, bytes_value):
        """
        Format bytes to human-readable format
        
        Args:
            bytes_value (int): Bytes to format
            
        Returns:
            str: Formatted string with appropriate unit
        """
        for unit in ['B', 'KB', 'MB', 'GB', 'TB', 'PB']:
            if bytes_value < 1024 or unit == 'PB':
                return f"{bytes_value:.2f} {unit}"
            bytes_value /= 1024 