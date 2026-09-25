#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Run narrowly constrained, read-only native system diagnostics."""

import os
import re
from typing import ClassVar

from qzx.commands.system._diagnostic_arguments import validate_unix_arguments
from qzx.commands.system._diagnostic_process import (
    _BoundedStreamCapture as _BoundedStreamCapture,
    _run_bounded_process,
    _subprocess_output_encoding as _subprocess_output_encoding,
)
from qzx.commands.system._diagnostic_workflow import execute_diagnostic
from qzx.core.command_base import CommandBase


class RunDiagnosticCommand(CommandBase):
    """Execute one read-only diagnostic with a strict argument grammar."""

    name = "runDiagnosticCommand"
    description = (
        "Runs a strictly read-only native system diagnostic from a "
        "platform-specific allowlist"
    )
    category = "system"
    allow_variadic_option_passthrough = True

    result_schema: ClassVar[dict[str, object]] = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "message": {"type": "string"},
            "error": {
                "oneOf": [
                    {"type": "string"},
                    {"type": "null"},
                ]
            },
            "error_code": {"type": "string"},
            "stdout": {"type": "string"},
            "stderr": {"type": "string"},
            "details": {
                "type": "object",
                "additionalProperties": True,
            },
        },
        "additionalProperties": True,
    }

    parameters = [
        {
            "name": "command",
            "description": (
                "Read-only diagnostic. Windows: hostname, ipconfig, netstat, "
                "whoami. Unix: cal, date, free, hostname, netstat, ss, "
                "uname, uptime, whoami"
            ),
            "required": True,
            "type": "str",
        },
        {
            "name": "args",
            "description": (
                "Arguments accepted by QZX's command-specific read-only grammar"
            ),
            "required": False,
            "default": [],
            "type": "str",
            "is_variadic": True,
        },
    ]

    examples = [
        {
            "command": "qzx runDiagnosticCommand hostname",
            "description": "Read the local system host name",
        },
        {
            "command": "qzx runDiagnosticCommand whoami",
            "description": "Read the current operating-system user",
        },
        {
            "command": "qzx runDiagnosticCommand uname -a",
            "description": "Read Unix kernel and architecture details",
        },
        {
            "command": "qzx runDiagnosticCommand ipconfig /all",
            "description": "Read the complete Windows network configuration",
        },
        {
            "command": "qzx runDiagnosticCommand netstat -an",
            "description": (
                "List connections numerically without name resolution"
            ),
        },
    ]

    TIMEOUT_SECONDS = 20
    STDOUT_LIMIT_BYTES = 128 * 1024
    STDERR_LIMIT_BYTES = 32 * 1024

    _COMMON_NO_ARGUMENTS = {"hostname", "whoami"}
    _WINDOWS_COMMANDS = {
        "hostname",
        "ipconfig",
        "netstat",
        "whoami",
    }
    _UNIX_COMMANDS = {
        "cal",
        "date",
        "free",
        "hostname",
        "netstat",
        "ss",
        "uname",
        "uptime",
        "whoami",
    }
    _TRUSTED_UNIX_DIRECTORIES = (
        "/usr/bin",
        "/bin",
        "/usr/sbin",
        "/sbin",
    )

    def execute(self, command, *args):
        return execute_diagnostic(
            self,
            _run_bounded_process,
            command,
            args,
        )

    @classmethod
    def _validate_arguments(cls, command_name, arguments, system_name):
        if any("\x00" in argument for argument in arguments):
            return "Arguments cannot contain NUL bytes."
        if command_name in cls._COMMON_NO_ARGUMENTS and arguments:
            return "'{}' accepts no arguments through QZX.".format(
                command_name
            )

        if system_name == "windows":
            return cls._validate_windows_arguments(command_name, arguments)
        return cls._validate_unix_arguments(command_name, arguments)

    @staticmethod
    def _validate_windows_arguments(command_name, arguments):
        if command_name == "ipconfig":
            return (
                None
                if arguments in ([], ["/all"])
                else "ipconfig permits only no arguments or '/all'; release, "
                "renew, flush, and registration operations are blocked."
            )
        if command_name == "netstat":
            valid = (
                bool(arguments)
                and all(
                    re.fullmatch(r"-[aners]+", argument.lower())
                    for argument in arguments
                )
                and any(
                    "n" in argument.lower()[1:]
                    for argument in arguments
                )
            )
            return (
                None
                if valid
                else "Windows netstat requires numeric output (-n) and "
                "accepts only combined read-only flags from -a, -n, -e, -r, "
                "and -s. Name resolution, process attribution, and remote "
                "targets are blocked."
            )
        return None if not arguments else "This diagnostic accepts no arguments."

    @staticmethod
    def _validate_unix_arguments(command_name, arguments):
        return validate_unix_arguments(command_name, arguments)

    @classmethod
    def _trusted_executable(cls, command_name, system_name):
        if system_name == "windows":
            system_directory = cls._windows_system_directory()
            if system_directory is None:
                return None
            candidate = os.path.join(
                system_directory,
                command_name + ".exe",
            )
            return candidate if os.path.isfile(candidate) else None

        trusted_roots = {
            os.path.realpath(directory)
            for directory in cls._TRUSTED_UNIX_DIRECTORIES
            if os.path.isdir(directory)
        }
        for directory in cls._TRUSTED_UNIX_DIRECTORIES:
            candidate = os.path.join(directory, command_name)
            if not os.path.isfile(candidate) or not os.access(
                candidate,
                os.X_OK,
            ):
                continue
            resolved = os.path.realpath(candidate)
            if os.path.dirname(resolved) in trusted_roots:
                return resolved
        return None

    @staticmethod
    def _windows_system_directory():
        """Ask Windows for System32 without trusting process environment."""
        try:
            import ctypes

            buffer = ctypes.create_unicode_buffer(32768)
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            get_system_directory = kernel32.GetSystemDirectoryW
            get_system_directory.argtypes = [
                ctypes.POINTER(ctypes.c_wchar),
                ctypes.c_uint,
            ]
            get_system_directory.restype = ctypes.c_uint
            length = get_system_directory(buffer, len(buffer))
        except (AttributeError, OSError):
            return None
        if length == 0 or length >= len(buffer):
            return None
        return buffer.value

    @classmethod
    def _diagnostic_environment(cls, executable, system_name):
        """Provide only non-secret environment needed by trusted utilities."""
        executable_directory = os.path.dirname(executable)
        if system_name == "windows":
            windows_directory = os.path.dirname(executable_directory)
            return {
                "SystemRoot": windows_directory,
                "WINDIR": windows_directory,
                "PATH": executable_directory,
                "PATHEXT": ".COM;.EXE;.BAT;.CMD",
            }

        environment = {
            "PATH": os.pathsep.join(cls._TRUSTED_UNIX_DIRECTORIES),
        }
        for name in ("LANG", "LC_ALL", "LC_CTYPE"):
            value = os.environ.get(name)
            if value and "\x00" not in value and len(value) <= 4096:
                environment[name] = value
        return environment

    @staticmethod
    def _failure(
        error_code,
        error,
        message,
        command_details,
        **extra_details,
    ):
        details = {"command": command_details}
        details.update(extra_details)
        return {
            "success": False,
            "error_code": error_code,
            "error": error,
            "message": message,
            "details": details,
        }
