#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Constrained bridge for a small allowlist of diagnostic system commands."""

import datetime
import os
import platform
import shutil
import subprocess
from pathlib import Path

from qzx.core.command_base import CommandBase


class CommandsBridgeCommand(CommandBase):
    """Execute diagnostic commands without invoking a shell."""

    name = "commandsBridge"
    aliases = ["bridge", "cmd", "run"]
    description = "Executes allowlisted diagnostic system commands with bounded output"
    category = "system"

    parameters = [
        {
            "name": "command",
            "description": "Allowlisted diagnostic command to execute",
            "required": True,
            "type": "str",
        },
        {
            "name": "args",
            "description": "Arguments passed directly to the command without shell expansion",
            "required": False,
            "default": [],
            "type": "str",
            "is_variadic": True,
        },
    ]

    examples = [
        {
            "command": "qzx commandsBridge pwd",
            "description": "Shows the current working directory",
        },
        {
            "command": "qzx bridge whoami",
            "description": "Shows the current operating-system user",
        },
        {
            "command": "qzx cmd ping 127.0.0.1",
            "description": "Runs a local network diagnostic",
        },
        {
            "command": "qzx run hostname",
            "description": "Shows the current host name",
        },
    ]

    SAFE_COMMANDS = {
        "cal",
        "date",
        "df",
        "du",
        "file",
        "free",
        "groups",
        "head",
        "host",
        "hostname",
        "id",
        "ifconfig",
        "ip",
        "ipconfig",
        "locate",
        "netstat",
        "nslookup",
        "ping",
        "printenv",
        "ps",
        "ss",
        "stat",
        "systeminfo",
        "tail",
        "tasklist",
        "type",
        "uname",
        "uptime",
        "wc",
        "where",
        "which",
        "who",
        "whoami",
    }
    BLOCKED_COMMANDS = {
        "bash",
        "chmod",
        "chown",
        "cmd",
        "cp",
        "dd",
        "del",
        "fdisk",
        "format",
        "git",
        "kill",
        "mkfs",
        "mkdir",
        "mv",
        "npm",
        "perl",
        "pip",
        "pkill",
        "powershell",
        "pwsh",
        "python",
        "reboot",
        "ren",
        "rm",
        "rmdir",
        "ruby",
        "sc",
        "sh",
        "shutdown",
        "start",
        "sudo",
        "systemctl",
        "touch",
        "wsl",
    }
    TIMEOUT_SECONDS = 30
    MAX_OUTPUT_CHARS = 200_000

    def execute(self, command, *args):
        command_name = str(command).strip().lower()
        argument_list = [str(value) for value in args]
        started_at = datetime.datetime.now(datetime.timezone.utc)
        command_details = {
            "name": command_name,
            "args": argument_list,
            "os": platform.system(),
            "started_at": started_at.isoformat(),
            "shell": False,
            "timeout_seconds": self.TIMEOUT_SECONDS,
        }

        if command_name == "pwd":
            current = str(Path.cwd())
            return {
                "success": True,
                "message": f"Current working directory: {current}",
                "stdout": current,
                "details": {"command": command_details, "directory": current},
            }

        if command_name == "cd":
            return self._change_directory(argument_list, command_details)

        if command_name == "clear":
            return {
                "success": True,
                "message": "Clear was acknowledged; no terminal escape sequences were emitted.",
                "details": {"command": command_details, "simulated": True},
            }

        if command_name == "exit":
            return {
                "success": True,
                "message": "Exit was acknowledged but the QZX process was not terminated.",
                "details": {"command": command_details, "simulated": True},
            }

        if command_name in self.BLOCKED_COMMANDS:
            return {
                "success": False,
                "error_code": "command_blocked",
                "error": f"Command '{command_name}' can mutate state or execute arbitrary code.",
                "message": "commandsBridge only permits bounded diagnostic commands.",
                "details": {"command": command_details},
            }

        if command_name not in self.SAFE_COMMANDS:
            return {
                "success": False,
                "error_code": "command_not_allowlisted",
                "error": f"Command '{command_name}' is not in the diagnostic allowlist.",
                "message": "Use a dedicated QZX command or execute the system tool directly after review.",
                "details": {
                    "command": command_details,
                    "allowed_commands": sorted(self.SAFE_COMMANDS),
                },
            }

        executable = shutil.which(command_name)
        if executable is None:
            return {
                "success": False,
                "error_code": "command_not_found",
                "error": f"Command '{command_name}' was not found in PATH.",
                "message": "Install the diagnostic tool or choose one available on this platform.",
                "details": {"command": command_details},
            }

        try:
            process = subprocess.run(
                [executable, *argument_list],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=False,
                timeout=self.TIMEOUT_SECONDS,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return {
                "success": False,
                "error_code": "command_timeout",
                "error": f"Command exceeded {self.TIMEOUT_SECONDS} seconds.",
                "message": "The diagnostic command was terminated after reaching its time limit.",
                "details": {
                    "command": command_details,
                    "stdout": self._bounded(exc.stdout or ""),
                    "stderr": self._bounded(exc.stderr or ""),
                },
            }
        except OSError as exc:
            return {
                "success": False,
                "error_code": "command_execution_failed",
                "error": str(exc),
                "message": f"Could not start diagnostic command '{command_name}'.",
                "details": {"command": command_details},
            }

        duration = (datetime.datetime.now(datetime.timezone.utc) - started_at).total_seconds()
        success = process.returncode == 0
        return {
            "success": success,
            "message": (
                f"Diagnostic command '{command_name}' completed successfully."
                if success
                else f"Diagnostic command '{command_name}' exited with code {process.returncode}."
            ),
            "error": None if success else self._bounded(process.stderr.strip() or "Non-zero exit status."),
            "stdout": self._bounded(process.stdout),
            "stderr": self._bounded(process.stderr),
            "details": {
                "command": command_details,
                "exit_code": process.returncode,
                "duration_seconds": duration,
                "output_truncated": (
                    len(process.stdout) > self.MAX_OUTPUT_CHARS
                    or len(process.stderr) > self.MAX_OUTPUT_CHARS
                ),
            },
        }

    def _change_directory(self, arguments, command_details):
        if len(arguments) > 1:
            return {
                "success": False,
                "error_code": "usage_error",
                "error": "cd accepts at most one directory.",
                "message": "Quote directory paths containing spaces.",
                "details": {"command": command_details},
            }
        target = Path(arguments[0]).expanduser() if arguments else Path.home()
        try:
            previous = Path.cwd()
            os.chdir(target)
            current = Path.cwd()
        except (FileNotFoundError, NotADirectoryError, PermissionError, OSError) as exc:
            return {
                "success": False,
                "error_code": "change_directory_failed",
                "error": str(exc),
                "message": f"Could not change directory to '{target}'.",
                "details": {"command": command_details},
            }
        return {
            "success": True,
            "message": f"Changed directory from '{previous}' to '{current}'.",
            "details": {
                "command": command_details,
                "previous_directory": str(previous),
                "current_directory": str(current),
            },
        }

    @classmethod
    def _bounded(cls, value):
        if isinstance(value, bytes):
            value = value.decode(errors="replace")
        text = str(value)
        if len(text) <= cls.MAX_OUTPUT_CHARS:
            return text
        return text[: cls.MAX_OUTPUT_CHARS] + "\n… output truncated by QZX …"
