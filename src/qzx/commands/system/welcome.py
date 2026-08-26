#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Professional, read-only onboarding for QZX."""

from qzx import __version__
from qzx.commands.system.terminal_welcome import TerminalWelcome
from qzx.core.command_base import CommandBase
from qzx.welcome_text import (
    COMMAND_CATALOG_URL,
    onboarding_plan,
    safety_guidance,
    welcome_summary,
)


class WelcomeCommand(CommandBase):
    """Introduce QZX and optionally render an explicit system snapshot."""

    name = "welcome"
    description = (
        "Introduces QZX with a read-only first-success path and optional "
        "system details"
    )
    category = "system"

    parameters = [
        {
            "name": "full_info",
            "description": (
                "Collect and show system, memory, and storage details; disabled "
                "by default for fast startup"
            ),
            "required": False,
            "default": False,
            "type": "bool",
        }
    ]

    examples = [
        {
            "command": "qzx welcome",
            "description": "Display the read-only onboarding screen immediately",
        },
        {
            "command": "qzx welcome true",
            "description": (
                "Collect system details, then display the detailed welcome screen"
            ),
        },
    ]

    def __init__(self, welcome_factory=None):
        """Accept a deterministic presentation boundary for testing."""
        self._welcome_factory = welcome_factory or TerminalWelcome

    def execute(self, full_info=False):
        """Return the canonical onboarding result without probing by default."""
        show_full_info = (
            False if full_info is None else self._parse_bool(full_info)
        )
        if show_full_info is None:
            return {
                "success": False,
                "message": "full_info must be true or false.",
                "error": "Invalid full_info value.",
                "error_code": "invalid_full_info",
                "welcome_displayed": False,
            }

        try:
            welcome_generator = self._welcome_factory(qzx_version=__version__)
            welcome_message = welcome_generator.get_welcome_message(
                show_full_info=show_full_info
            )
            return {
                "success": True,
                "message": welcome_summary(
                    __version__,
                    detailed=show_full_info,
                ),
                "output": welcome_message,
                "welcome_displayed": True,
                "info_level": "detailed" if show_full_info else "basic",
                "qzx_version": __version__,
                "onboarding": onboarding_plan(),
                "documentation_url": COMMAND_CATALOG_URL,
                "safety": safety_guidance(),
            }
        except Exception as exc:
            return {
                "success": False,
                "message": "QZX could not render the welcome screen.",
                "error": "Welcome presentation failed.",
                "error_code": "welcome_presentation_failed",
                "exception_type": type(exc).__name__,
                "welcome_displayed": False,
            }
