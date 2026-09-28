#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""IsAdmin Command - checks current administrative privileges."""

import ctypes
import getpass
import os
import platform
import subprocess

from qzx.commands.system._admin_status import inspect_admin_status
from qzx.core.command_base import CommandBase


class IsAdminCommand(CommandBase):
    """Command to check if the current user has administrative privileges."""

    name = "isAdmin"
    description = "Checks if the current user has administrative privileges"
    category = "system"

    parameters = []

    examples = [
        {
            "command": "qzx isAdmin",
            "description": "Check if the current user has administrative privileges",
        }
    ]

    def execute(self):
        """Check current administrative privileges using platform evidence."""
        try:
            return inspect_admin_status(
                platform.system(),
                run_command=subprocess.run,
                username_provider=getpass.getuser,
                uid_provider=lambda: os.getuid(),
                windows_admin_provider=lambda: (
                    ctypes.windll.shell32.IsUserAnAdmin() != 0
                ),
            )
        except Exception as exc:
            error_message = (
                f"Error checking administrative privileges: {exc}"
            )
            return {
                "success": False,
                "error": error_message,
                "message": (
                    "Failed to determine administrative status: "
                    f"{exc}"
                ),
                "is_admin": False,
            }
