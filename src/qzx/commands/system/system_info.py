#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Return a structured, opt-in system and environment report."""

import getpass
import os
import platform
import sys

from qzx import __version__
from qzx.core.command_base import CommandBase


class SystemInfoCommand(CommandBase):
    """Inspect portable host facts, with costlier sections on demand."""

    name = "systemInfo"
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
            "command": "qzx systemInfo",
            "description": "Get a fast, portable system summary",
        },
        {
            "command": "qzx systemInfo --detailed",
            "description": "Add current RAM and storage details",
        },
        {
            "command": "qzx systemInfo --include-environment",
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
        try:
            detailed = self._normalize_bool(detailed)
            include_environment = self._normalize_bool(include_environment)
        except ValueError as exc:
            return {
                "success": False,
                "error_code": "invalid_boolean",
                "error": str(exc),
                "message": (
                    "The detailed and include_environment values must each be "
                    "true or false."
                ),
                "details": {
                    "detailed": detailed,
                    "include_environment": include_environment,
                },
            }

        try:
            info = self._collect_core_info(include_environment)
        except (OSError, RuntimeError, ValueError) as exc:
            return {
                "success": False,
                "error_code": "system_info_unavailable",
                "error": f"{type(exc).__name__}: {exc}",
                "message": (
                    "QZX could not collect the portable system summary. "
                    "Verify that the current directory and operating-system "
                    "account information are accessible, then retry."
                ),
                "details": {
                    "detailed_requested": detailed,
                    "environment_requested": include_environment,
                },
            }

        warnings = []
        if detailed:
            details, detail_warnings = self._details_collector()
            info.update(details)
            warnings.extend(detail_warnings)

        message = self._build_message(
            info,
            detailed=detailed,
            include_environment=include_environment,
            warnings=warnings,
        )
        return {
            "success": True,
            "message": message,
            "system_info": info,
            "details_requested": detailed,
            "environment_included": include_environment,
            "warnings": warnings,
        }

    @classmethod
    def _normalize_bool(cls, value):
        parsed = cls._parse_bool(value)
        if parsed is None:
            raise ValueError(f"Expected a boolean value, received {value!r}.")
        return parsed

    def _collect_core_info(self, include_environment):
        system_name = platform.system()
        machine = platform.machine()
        info = {
            "qzx": {"version": __version__},
            "os": system_name,
            "os_version": platform.version(),
            "os_release": platform.release(),
            "machine": machine,
            "processor": platform.processor() or "unknown",
            "architecture": {
                "bits": 64 if sys.maxsize > 2**32 else 32,
                "machine": machine,
            },
            "platform": sys.platform,
            "python": {
                "version": platform.python_version(),
                "implementation": platform.python_implementation(),
                "compiler": platform.python_compiler(),
                "build": list(platform.python_build()),
            },
            "network": {"hostname": platform.node() or "unknown"},
            "user": {
                "username": self._current_username(),
                "home_directory": os.path.expanduser("~"),
            },
            "environment": {
                "current_directory": os.getcwd(),
                "variables_included": include_environment,
            },
        }

        if include_environment:
            info["environment"]["environment_variables"] = (
                self._get_important_env_vars()
            )

        if system_name == "Windows":
            info["windows"] = {
                "edition": platform.win32_edition(),
                "version": list(platform.win32_ver()),
            }
        elif system_name == "Linux":
            linux_info = {"libc": list(platform.libc_ver())}
            try:
                linux_info["distribution"] = (
                    platform.freedesktop_os_release()
                )
            except OSError:
                pass
            info["linux"] = linux_info
        elif system_name == "Darwin":
            info["macos"] = {"version": list(platform.mac_ver())}

        return info

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
        python_info = info["python"]
        message = (
            "System: {} {} on {} ({}-bit). Python {} {}. "
            "Host: {}; user: {}; current directory: {}.".format(
                info["os"],
                info["os_release"],
                info["machine"] or "unknown architecture",
                info["architecture"]["bits"],
                python_info["implementation"],
                python_info["version"],
                info["network"]["hostname"],
                info["user"]["username"],
                info["environment"]["current_directory"],
            )
        )

        if detailed:
            available = [
                label
                for field, label in (
                    ("memory", "RAM"),
                    ("storage", "storage"),
                )
                if field in info
            ]
            message += " Detailed sections: {}.".format(
                ", ".join(available) if available else "none available"
            )
            message += (
                " GPU discovery stays opt-in through 'qzx getGpuInfo' "
                "because it may invoke native vendor tools."
            )
        else:
            message += (
                " Add --detailed for RAM and storage without probing GPUs."
            )

        if include_environment:
            count = len(
                info["environment"].get("environment_variables", {})
            )
            message += f" Included {count} selected environment variables."
        else:
            message += (
                " Environment-variable values were not included; add "
                "--include-environment to request them locally."
            )

        if warnings:
            message += " Partial-data warnings: {}.".format(len(warnings))
        return message

    def _get_important_env_vars(self):
        """Return only the documented local allowlist; never expand it implicitly."""
        return {
            name: self._environ[name]
            for name in self._environment_variable_allowlist
            if name in self._environ
        }
