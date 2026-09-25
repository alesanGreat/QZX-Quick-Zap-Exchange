#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
GetCpuLoad Command - Retrieves information about CPU usage
"""

import psutil

from qzx.commands.system._cpu_load_snapshot import execute_cpu_load
from qzx.core.command_base import CommandBase

class GetCpuLoadCommand(CommandBase):
    """
    Command to get CPU load information
    """
    
    name = "getCpuLoad"
    description = "Gets information about current CPU usage"
    category = "system"
    
    parameters = [
        {
            'name': 'interval',
            'description': 'Time interval (in seconds) to calculate CPU usage',
            'required': False,
            'default': 1.0,
            'type': 'float'
        }
    ]
    
    examples = [
        {
            'command': 'qzx getCpuLoad',
            'description': 'Get CPU usage information with 1-second interval'
        },
        {
            'command': 'qzx getCpuLoad 0.5',
            'description': 'Get CPU usage information with 0.5-second interval'
        }
    ]
    
    def __init__(self, psutil_module=None):
        """Allow deterministic CPU providers while keeping psutil as the default."""
        self._psutil = psutil_module or psutil

    def execute(self, interval=1):
        """Return one normalized CPU load snapshot."""
        return execute_cpu_load(self, interval)
