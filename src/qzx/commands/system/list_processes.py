#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ListProcesses Command - Lists running processes
"""

import platform

from qzx.commands.system._process_inventory import (
    CPU_SAMPLE_SECONDS,
    DEFAULT_LIMIT,
    execute_processes,
    wait_for_cpu_sample,
)
from qzx.commands.system._windows_process_snapshot import windows_process_snapshot
from qzx.core.command_base import CommandBase

class ListProcessesCommand(CommandBase):
    """
    Command to list running processes
    """
    
    name = "listProcesses"
    description = (
        "Lists running processes with real CPU usage sampled over "
        f"{CPU_SAMPLE_SECONDS:g} s (similar to 'ps'/'top')"
    )
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
            'description': (
                f'Maximum number of processes to return (default {DEFAULT_LIMIT}; '
                '0 or null returns every process)'
            ),
            'required': False,
            'default': DEFAULT_LIMIT
        }
    ]
    
    examples = [
        {
            'command': 'qzx listProcesses',
            'description': f'List the {DEFAULT_LIMIT} processes using the most CPU right now'
        },
        {
            'command': 'qzx listProcesses python',
            'description': 'List processes containing "python" in their name'
        },
        {
            'command': 'qzx listProcesses null memory 10',
            'description': 'List the top 10 processes by memory usage'
        },
        {
            'command': 'qzx listProcesses null pid 0',
            'description': 'List every running process ordered by PID'
        }
    ]
    
    @staticmethod
    def _load_psutil():
        """Load psutil lazily so command discovery remains resilient."""
        import psutil

        return psutil

    @staticmethod
    def _platform_system():
        """Operating-system name; tests inject a fixed platform."""
        return platform.system()

    @staticmethod
    def _process_snapshot():
        """One native Windows process snapshot, or None to use psutil."""
        return windows_process_snapshot()

    @staticmethod
    def _wait_for_cpu_sample(seconds):
        """Wait between the two CPU readings; tests override it."""
        wait_for_cpu_sample(seconds)

    def execute(self, filter_str=None, sort_by='cpu', limit=None):
        """List running processes using the normalized process inventory."""
        return execute_processes(self, filter_str, sort_by, limit)
