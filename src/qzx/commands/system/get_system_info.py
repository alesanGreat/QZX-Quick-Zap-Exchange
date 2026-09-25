#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Return a structured, opt-in system and environment report."""

import getpass
import os

from qzx.commands.system._system_info_core import collect_core_info
from qzx.commands.system._system_info_workflow import (
    build_system_info_message,
    execute_system_info,
)
from qzx.core.command_base import CommandBase


class GetSystemInfoCommand(CommandBase):
    """Inspect portable host facts, with costlier sections on demand."""

    name = "getSystemInfo"
    description = (
        "Gets portable operating-system, Python, user, and environment "
        "information with optional RAM and storage details"
    )
    category = "system"

    parameters = [
        {
            "name": "detailed",
            "description": (
                "Include RAM and storage details (true/false; defaults to false)"
            ),
            "required": False,
            "default": False,
            "type": "bool",
        },
        {
            "name": "include_environment",
            "description": (
                "Include selected local environment-variable values "
                "(true/false; defaults to false)"
            ),
            "required": False,
            "default": False,
            "type": "bool",
        },
    ]

    examples = [
        {
            "command": "qzx getSystemInfo",
            "description": "Get a fast, portable system summary",
        },
        {
            "command": "qzx getSystemInfo --detailed",
            "description": "Add current RAM and storage details",
        },
        {
            "command": "qzx getSystemInfo --include-environment",
            "description": "Include selected local environment variables",
        },
    ]

    _environment_variable_allowlist = (
        "PATH",
        "PYTHONPATH",
        "LANG",
        "USER",
        "HOME",
        "TEMP",
        "TMP",
        "SHELL",
        "LOGNAME",
        "USERNAME",
        "COMPUTERNAME",
        "HOSTNAME",
    )

    def __init__(self, *, environ=None, details_collector=None):
        """Accept process and probe boundaries explicitly for reliable tests."""
        self._environ = environ if environ is not None else os.environ
        self._details_collector = (
            details_collector
            if details_collector is not None
            else self._collect_details
        )

    def execute(self, detailed=False, include_environment=False):
        """Build the requested report without emitting side-effect output."""
        return execute_system_info(self, detailed, include_environment)

    @classmethod
    def _normalize_bool(cls, value):
        parsed = cls._parse_bool(value)
        if parsed is None:
            raise ValueError(f"Expected a boolean value, received {value!r}.")
        return parsed

    def _collect_core_info(self, include_environment):
        return collect_core_info(self, include_environment)

    @staticmethod
    def _current_username():
        try:
            return getpass.getuser()
        except (ImportError, KeyError, OSError):
            return "unknown"

    @staticmethod
    def _collect_details():
        from qzx.commands.system.get_disk_space import GetDiskSpaceCommand
        from qzx.commands.system.get_ram_info import GetRamInfoCommand

        details = {}
        warnings = []
        probes = (
            ("memory", GetRamInfoCommand(), "ram_info"),
            ("storage", GetDiskSpaceCommand(), None),
        )
        for section, command, payload_field in probes:
            result = command.execute()
            if result.get("success"):
                if payload_field is None:
                    details[section] = {
                        "summary": result.get("summary", {}),
                        "disks": result.get("disks", []),
                    }
                else:
                    details[section] = result.get(payload_field, {})
                continue
            warnings.append(
                "{} details were unavailable: {}".format(
                    section.capitalize(),
                    result.get("error") or result.get("message", "unknown error"),
                )
            )
        return details, warnings

    @staticmethod
    def _build_message(
        info,
        *,
        detailed,
        include_environment,
        warnings,
    ):
        return build_system_info_message(
            info,
            detailed=detailed,
            include_environment=include_environment,
            warnings=warnings,
        )

    def _get_important_env_vars(self):
        """Return only the documented local allowlist; never expand it implicitly."""
        return {
            name: self._environ[name]
            for name in self._environment_variable_allowlist
            if name in self._environ
        }
