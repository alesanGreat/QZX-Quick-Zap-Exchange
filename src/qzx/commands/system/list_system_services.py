#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""List services through the real native manager of the running system."""

import shutil
import subprocess

from qzx.commands.system._service_collectors import (
    collect_freebsd_services,
    collect_launchd_services,
    collect_linux_services,
    collect_openbsd_services,
    collect_smf_services,
    collect_windows_services,
)
from qzx.commands.system._service_parsers import (
    parse_openrc_status,
    parse_sc_query,
)
from qzx.commands.system._service_workflow import execute_system_services
from qzx.core.command_base import CommandBase


class ListSystemServicesCommand(CommandBase):
    """Inspect active and stopped services through the native manager."""

    name = "listSystemServices"
    description = "Lists operating-system services and their running status"
    category = "system"

    parameters = [
        {
            "name": "status",
            "description": (
                "Filter by service status (running, stopped, all; "
                "defaults to all)"
            ),
            "required": False,
            "default": "all",
        }
    ]

    examples = [
        {
            "command": "qzx listSystemServices",
            "description": "List all system services",
        },
        {
            "command": "qzx listSystemServices running",
            "description": "List only active running system services",
        },
    ]

    def __init__(self, executable_finder=None, command_runner=None):
        """Accept native boundaries explicitly for deterministic fallback tests."""
        self._executable_finder = executable_finder or shutil.which
        self._command_runner = command_runner or self._run

    def execute(self, status="all"):
        """List services through the current operating system's native manager."""
        return execute_system_services(self, status)

    @staticmethod
    def _run(command, timeout=10):
        return subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )

    def _collect_windows_services(self):
        return collect_windows_services(self)

    def _collect_linux_services(self):
        return collect_linux_services(self)

    def _collect_launchd_services(self):
        return collect_launchd_services(self)

    def _collect_freebsd_services(self):
        return collect_freebsd_services(self)

    def _collect_openbsd_services(self):
        return collect_openbsd_services(self)

    def _collect_smf_services(self):
        return collect_smf_services(self)

    @staticmethod
    def _parse_openrc_status(stdout):
        return parse_openrc_status(stdout)

    @staticmethod
    def _parse_sc_query(stdout):
        return parse_sc_query(stdout)
