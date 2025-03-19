#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
GetDiskName Command - Retrieves disk name/model information
"""

import os
import platform
import subprocess
import psutil
from Core.command_base import CommandBase

class GetDiskNameCommand(CommandBase):
    """
    Command to get disk name/model information
    """
    
    name = "getDiskName"
    description = "Gets disk name/model information for a disk or all disks"
    category = "system"
    
    parameters = [
        {
            'name': 'disk_path',
            'description': 'Path to the disk to get information for. If not provided, shows information for all disks',
            'required': False,
            'default': None
        }
    ]
    
    examples = [
        {
            'command': 'qzx getDiskName',
            'description': 'Get information about all disks'
        },
        {
            'command': 'qzx getDiskName C:',
            'description': 'Get information about the C: drive (Windows)'
        },
        {
            'command': 'qzx getDiskName /dev/sda',
            'description': 'Get information about the /dev/sda disk (Linux)'
        }
    ]
    
    def execute(self, disk_path=None):
        """
        Gets disk name/model information
        
        Args:
            disk_path (str, optional): Path to the disk to get information for.
                                      If not provided, shows information for all disks.
            
        Returns:
            Dictionary with disk information
        """
        try:
            os_type = platform.system().lower()
            result = {
                "os_type": os_type,
                "disks": []
            }
            
            # If specific disk is provided
            if disk_path:
                # Check if disk exists
                if not os.path.exists(disk_path):
                    return f"Error: Disk path '{disk_path}' does not exist"
                
                disk_info = self._get_disk_info(disk_path, os_type)
                if disk_info:
                    result["disks"].append(disk_info)
            else:
                # List all disks
                if os_type == "windows":
                    # Get logical drives
                    partitions = psutil.disk_partitions(all=False)
                    for partition in partitions:
                        disk_info = self._get_disk_info(partition.device, os_type)
                        if disk_info:
                            result["disks"].append(disk_info)
                    
                    # Try to get physical disk information
                    try:
                        # Get physical disk info
                        wmic_output = subprocess.run(
                            ["wmic", "diskdrive", "get", "DeviceID,Model,Size,MediaType,InterfaceType"],
                            capture_output=True,
                            text=True,
                            check=False
                        )
                        
                        # Parse wmic output
                        lines = wmic_output.stdout.strip().split('\n')
                        if len(lines) > 1:  # First line is header
                            result["physical_disks"] = []
                            headers = lines[0].strip().split()
                            for line in lines[1:]:
                                if line.strip():
                                    values = line.strip().split(None, len(headers) - 1)
                                    disk_data = {}
                                    for i, header in enumerate(headers):
                                        if i < len(values):
                                            disk_data[header.lower()] = values[i]
                                    result["physical_disks"].append(disk_data)
                    except Exception as e:
                        result["physical_disks_error"] = str(e)
                
                elif os_type == "linux":
                    # For Linux, get all block devices
                    try:
                        lsblk_output = subprocess.run(
                            ["lsblk", "-o", "NAME,MODEL,SIZE,FSTYPE,MOUNTPOINT", "-J"],
                            capture_output=True,
                            text=True,
                            check=False
                        )
                        
                        # Try to parse JSON output
                        import json
                        try:
                            lsblk_data = json.loads(lsblk_output.stdout)
                            result["block_devices"] = lsblk_data
                        except json.JSONDecodeError:
                            # Fallback to regular output
                            lsblk_output = subprocess.run(
                                ["lsblk", "-o", "NAME,MODEL,SIZE,FSTYPE,MOUNTPOINT"],
                                capture_output=True,
                                text=True,
                                check=False
                            )
                            result["block_devices_raw"] = lsblk_output.stdout.strip()
                    except Exception as e:
                        result["block_devices_error"] = str(e)
                    
                    # Get partitions from psutil
                    partitions = psutil.disk_partitions(all=False)
                    for partition in partitions:
                        disk_info = self._get_disk_info(partition.device, os_type)
                        if disk_info:
                            result["disks"].append(disk_info)
                
                elif os_type == "darwin":  # macOS
                    # For macOS, list all disks
                    try:
                        diskutil_output = subprocess.run(
                            ["diskutil", "list", "-plist"],
                            capture_output=True,
                            text=True,
                            check=False
                        )
                        
                        # Try to parse plist output
                        import plistlib
                        try:
                            diskutil_data = plistlib.loads(diskutil_output.stdout.encode('utf-8'))
                            result["disk_list"] = diskutil_data
                        except:
                            # Fallback to regular output
                            diskutil_output = subprocess.run(
                                ["diskutil", "list"],
                                capture_output=True,
                                text=True,
                                check=False
                            )
                            result["disk_list_raw"] = diskutil_output.stdout.strip()
                    except Exception as e:
                        result["disk_list_error"] = str(e)
                    
                    # Get partitions from psutil
                    partitions = psutil.disk_partitions(all=False)
                    for partition in partitions:
                        disk_info = self._get_disk_info(partition.device, os_type)
                        if disk_info:
                            result["disks"].append(disk_info)
                
                else:
                    return f"Error: Unsupported operating system: {os_type}"
            
            return result
        except Exception as e:
            return f"Error getting disk name information: {str(e)}"
    
    def _get_disk_info(self, disk_path, os_type):
        """
        Get disk information for a specific disk
        
        Args:
            disk_path: Path to the disk
            os_type: Operating system type
            
        Returns:
            Dictionary with disk information
        """
        try:
            result = {
                "path": disk_path
            }
            
            # Add partitions info
            try:
                if os.path.exists(disk_path):
                    usage = psutil.disk_usage(disk_path)
                    result.update({
                        "total": usage.total,
                        "total_readable": self._format_bytes(usage.total),
                        "used": usage.used,
                        "used_readable": self._format_bytes(usage.used),
                        "free": usage.free,
                        "free_readable": self._format_bytes(usage.free),
                        "percent": usage.percent
                    })
            except:
                pass
            
            # Add OS-specific disk info
            if os_type == "windows":
                # Windows-specific info
                if ":" in disk_path:
                    # Logical drive
                    drive_letter = os.path.splitdrive(disk_path)[0].replace(":", "")
                    try:
                        # Get volume information
                        wmic_output = subprocess.run(
                            ["wmic", "logicaldisk", "where", f"DeviceID='{drive_letter}:'", "get", "VolumeName,FileSystem,Size,FreeSpace"],
                            capture_output=True,
                            text=True,
                            check=False
                        )
                        result["volume_info"] = wmic_output.stdout.strip()
                    except:
                        pass
                else:
                    # Physical drive
                    try:
                        wmic_output = subprocess.run(
                            ["wmic", "diskdrive", "where", f"DeviceID='{disk_path}'", "get", "Model,Size,MediaType,InterfaceType"],
                            capture_output=True,
                            text=True,
                            check=False
                        )
                        result["disk_info"] = wmic_output.stdout.strip()
                    except:
                        pass
            
            elif os_type == "linux":
                # Linux-specific info
                try:
                    # Get disk info with lsblk
                    lsblk_output = subprocess.run(
                        ["lsblk", "-o", "NAME,MODEL,SIZE,FSTYPE,MOUNTPOINT", disk_path],
                        capture_output=True,
                        text=True,
                        check=False
                    )
                    result["lsblk_info"] = lsblk_output.stdout.strip()
                    
                    # Try to get additional info with hdparm
                    try:
                        hdparm_output = subprocess.run(
                            ["hdparm", "-i", disk_path],
                            capture_output=True,
                            text=True,
                            check=False
                        )
                        if hdparm_output.returncode == 0:
                            result["hdparm_info"] = hdparm_output.stdout.strip()
                    except:
                        pass
                except:
                    pass
            
            elif os_type == "darwin":  # macOS
                # macOS-specific info
                try:
                    # Get disk info with diskutil
                    diskutil_output = subprocess.run(
                        ["diskutil", "info", disk_path],
                        capture_output=True,
                        text=True,
                        check=False
                    )
                    result["diskutil_info"] = diskutil_output.stdout.strip()
                except:
                    pass
            
            return result
        except:
            return None
    
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