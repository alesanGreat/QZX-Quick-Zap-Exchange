#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Clear one interactive terminal without invoking a command shell."""

from __future__ import annotations

import os
import sys

from qzx.core.command_base import CommandBase


class ClearScreenCommand(CommandBase):
    """Clear an attached terminal with a direct ANSI control sequence."""

    name = "clearScreen"
    description = (
        "Clears an interactive terminal directly without spawning cls, clear, "
        "or a command shell"
    )
    category = "system"

    parameters = []

    examples = [
        {
            "command": "qzx clearScreen",
            "description": "Clear the attached interactive terminal",
        }
    ]

    _CLEAR_SEQUENCE = "\x1b[2J\x1b[H"

    def __init__(self, *, stream=None, environment=None):
        super().__init__()
        self._stream = stream
        self._environment = environment

    def execute(self):
        """Clear only a real terminal; redirected output remains untouched."""
        stream = self._stream if self._stream is not None else sys.stdout
        environment = (
            self._environment
            if self._environment is not None
            else os.environ
        )

        if not self._is_interactive(stream):
            return self._not_cleared(
                "non_interactive_output",
                "Screen clearing was skipped because stdout is redirected or "
                "not attached to a terminal.",
            )
        if str(environment.get("TERM", "")).strip().casefold() == "dumb":
            return self._not_cleared(
                "terminal_declared_dumb",
                "Screen clearing was skipped because TERM=dumb declares no "
                "cursor-control support.",
            )

        try:
            stream.write(self._CLEAR_SEQUENCE)
            stream.flush()
        except Exception as exc:
            return {
                "success": False,
                "error_code": "screen_clear_failed",
                "error": f"{type(exc).__name__}: {exc}",
                "message": "QZX could not clear the attached terminal.",
                "screen_cleared": False,
                "details": {
                    "method": "ansi_csi",
                    "sequence_written": False,
                    "shell_spawned": False,
                },
            }

        return {
            "success": True,
            "message": "Interactive terminal cleared.",
            "screen_cleared": True,
            "details": {
                "method": "ansi_csi",
                "sequence_written": True,
                "shell_spawned": False,
            },
        }

    @staticmethod
    def _is_interactive(stream):
        try:
            return bool(stream.isatty())
        except (AttributeError, OSError, ValueError):
            return False

    @staticmethod
    def _not_cleared(reason, message):
        return {
            "success": True,
            "message": message,
            "screen_cleared": False,
            "details": {
                "method": "none",
                "reason": reason,
                "sequence_written": False,
                "shell_spawned": False,
            },
        }
