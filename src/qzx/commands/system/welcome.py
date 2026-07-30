#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Welcome Command - Displays the system welcome information
"""

from qzx import __version__
from qzx.core.command_base import CommandBase

# Import the welcome module
from qzx.commands.system.terminal_welcome import TerminalWelcome

class WelcomeCommand(CommandBase):
    """
    Command to display the system welcome information
    """
    
    name = "welcome"
    aliases = ["hello", "hi"]
    description = (
        "Displays the QZX welcome immediately, with optional system details"
    )
    category = "system"
    
    parameters = [
        {
            'name': 'full_info',
            'description': (
                'Collect and show system, memory, and storage details; disabled '
                'by default for fast startup'
            ),
            'required': False,
            'default': False,
            'type': 'bool'
        }
    ]
    
    examples = [
        {
            'command': 'qzx Welcome',
            'description': 'Display the welcome screen immediately'
        },
        {
            'command': 'qzx Welcome true',
            'description': 'Collect system details, then display the detailed welcome screen'
        }
    ]

    def __init__(self, welcome_factory=None):
        """Accept a deterministic presentation boundary for testing."""
        self._welcome_factory = welcome_factory or TerminalWelcome
    
    def execute(self, full_info=False):
        """
        Display the welcome screen with system information
        
        Args:
            full_info (str): Whether to show full information ('true' or 'false')
            
        Returns:
            Dictionary with the operation result
        """
        try:
            # Convert parameter to boolean
            if isinstance(full_info, str):
                show_full_info = full_info.lower() in ('true', 'yes', 'y', '1', 't')
            else:
                show_full_info = bool(full_info)
            
            # Instantiate the welcome generator
            welcome_generator = self._welcome_factory(qzx_version=__version__)
            
            # Get the formatted message
            welcome_message = welcome_generator.get_welcome_message(
                show_full_info=show_full_info
            )
            
            # Create a detailed description of what was displayed
            info_level = "detailed" if show_full_info else "basic"
            message = (
                f"QZX welcome screen ({info_level} view) displayed. "
                f"Version {__version__}."
            )
            
            return {
                "success": True,
                "message": message,
                "output": welcome_message,
                "welcome_displayed": True,
                "info_level": info_level,
                "qzx_version": __version__
            }
            
        except Exception as e:
            error_message = f"Error displaying welcome screen: {str(e)}"
            return {
                "success": False,
                "error": error_message,
                "message": f"Failed to display QZX welcome screen: {str(e)}",
                "welcome_displayed": False
            } 
