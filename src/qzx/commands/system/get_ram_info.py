#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
GetRamInfo Command - Retrieves information about system RAM
"""

import psutil

from qzx.commands.system._ram_inventory import execute_ram_info
from qzx.core.command_base import CommandBase

class GetRamInfoCommand(CommandBase):
    """
    Command to get information about system RAM
    """
    
    name = "getRamInfo"
    description = "Gets detailed information about system RAM usage"
    category = "system"
    
    parameters = []
    
    examples = [
        {
            'command': 'qzx getRamInfo',
            'description': 'Get detailed information about system memory usage'
        }
    ]

    def __init__(
        self,
        virtual_memory_provider=None,
        swap_memory_provider=None,
    ):
        """Allow deterministic providers without patching psutil at runtime."""

        self._virtual_memory = (
            virtual_memory_provider or psutil.virtual_memory
        )
        self._swap_memory = swap_memory_provider or psutil.swap_memory

    def execute(self):
        """Return normalized RAM and swap information."""
        return execute_ram_info(self)
