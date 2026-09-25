#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
GetCurrentUser Command - Retrieves information about the currently logged in user
"""

from qzx.commands.system._current_user_snapshot import execute_current_user
from qzx.core.command_base import CommandBase

class GetCurrentUserCommand(CommandBase):
    """
    Command to get information about the currently logged in user
    """
    
    name = "getCurrentUser"
    description = "Gets information about the currently logged in user"
    category = "system"
    
    parameters = []
    
    examples = [
        {
            'command': 'qzx getCurrentUser',
            'description': 'Get detailed information about the currently logged in user'
        }
    ]
    
    def execute(self):
        """Return a structured snapshot of the currently logged-in user."""
        return execute_current_user(self)
