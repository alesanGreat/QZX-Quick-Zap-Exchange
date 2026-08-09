#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Return the installed QZX version and stable product identity."""

from qzx import __version__
from qzx.core.command_base import CommandBase
from qzx.identity import product_identity


class VersionCommand(CommandBase):
    """Report QZX identity without duplicating host or capability discovery."""

    name = "version"
    description = "Displays the installed QZX version and product identity"
    category = "system"

    parameters = []

    examples = [
        {
            "command": "qzx version",
            "description": "Display the installed QZX version and product identity",
        },
        {
            "command": "qzx --version",
            "description": "Display the installed QZX version using the global flag",
        },
    ]

    def execute(self):
        """Return stable package identity; host facts belong to getSystemInfo."""

        identity = product_identity()
        return {
            "success": True,
            "message": f"QZX {__version__} — Quick Zap Exchange.",
            "version": __version__,
            "attribution": identity["attribution"],
            "license": identity["license"],
        }
