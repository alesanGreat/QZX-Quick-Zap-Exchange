#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""About command for QZX product identity and licensing."""

from qzx import __version__
from qzx.core.command_base import CommandBase
from qzx.identity import product_identity


class AboutCommand(CommandBase):
    """Display the canonical QZX creator, maintainer, and license details."""

    name = "about"
    description = "Displays QZX product, creator, maintainer, and license details"
    category = "system"
    parameters = []
    examples = [
        {
            "command": "qzx about",
            "description": "Display QZX product and attribution details",
        },
    ]

    def execute(self):
        """Return the canonical installed-package identity."""
        identity = product_identity()
        message = (
            "{attribution}\n\n"
            "QZX is a free and open-source command-line tool for people, "
            "automation, and AI agents. Licensed under {license}."
        ).format(**identity)
        return {
            "success": True,
            "message": message,
            "attribution": identity["attribution"],
            "product": {
                "name": identity["name"],
                "full_name": identity["full_name"],
                "version": __version__,
            },
            "author": {
                "name": identity["author"],
                "roles": ["creator", "maintainer"],
            },
            "license": {
                "spdx": identity["license"],
                "url": identity["license_url"],
            },
        }
