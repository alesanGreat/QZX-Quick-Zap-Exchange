#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ListProcesses Command - Lists running processes
"""

from qzx.commands.system._process_inventory import execute_processes
from qzx.core.command_base import CommandBase

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
    
    @staticmethod
    def _load_psutil():
        """Load psutil lazily so command discovery remains resilient."""
        import psutil

        return psutil

    def execute(self, filter_str=None, sort_by='cpu', limit=0):
        """List running processes using the normalized process inventory."""
        return execute_processes(self, filter_str, sort_by, limit)
