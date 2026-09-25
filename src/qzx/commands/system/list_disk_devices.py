#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ListDiskDevices Command - Retrieves disk name/model information
"""

from qzx.commands.system._disk_device_details import get_disk_info
from qzx.commands.system._disk_device_inventory import execute_disk_devices
from qzx.core.command_base import CommandBase

class ListDiskDevicesCommand(CommandBase):
    """
    Command to get disk name/model information
    """
    
    name = "listDiskDevices"
    description = "Gets disk name/model information for a disk or all disks"
    category = "system"
    _byte_units = ("B", "KB", "MB", "GB", "TB", "PB")
    
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
            'command': 'qzx listDiskDevices',
            'description': 'Get information about all disks'
        },
        {
            'command': 'qzx listDiskDevices C:',
            'description': 'Get information about the C: drive (Windows)'
        },
        {
            'command': 'qzx listDiskDevices /dev/sda',
            'description': 'Get information about the /dev/sda disk (Linux)'
        }
    ]
    
    def execute(self, disk_path=None):
        """Get disk information for one path or all mounted disks."""
        return execute_disk_devices(self, disk_path)

    def _get_disk_info(self, disk_path, os_type):
        """Return usage plus platform-specific information for one disk."""
        return get_disk_info(self, disk_path, os_type)
