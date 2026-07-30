#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Compatibility wrapper for the former generic native-command bridge."""

from pathlib import Path

from qzx.commands.system.run_diagnostic_command import RunDiagnosticCommand


class CommandsBridgeCommand(RunDiagnosticCommand):
    """Delegate historical invocations to the read-only replacement."""

    name = "commandsBridge"
    aliases = ["bridge", "cmd", "run"]
    _LEGACY_BLOCKED_COMMANDS = {
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
    description = (
        "Compatibility interface for runDiagnosticCommand; retained "
        "temporarily for QZX 0.2.x scripts"
    )
    result_schema = {
        **RunDiagnosticCommand.result_schema,
        "properties": {
            **RunDiagnosticCommand.result_schema["properties"],
            "deprecated": {"type": "boolean"},
            "replacement": {"type": "string"},
            "supported_through": {"type": "string"},
        },
    }
    examples = [
        {
            "command": "qzx commandsBridge hostname",
            "description": (
                "Run a legacy invocation through runDiagnosticCommand"
            ),
        },
        {
            "command": "qzx commandsBridge whoami",
            "description": "Read the current user during migration",
        },
    ]

    def execute(self, command, *args):
        command_name = str(command).strip().lower()
        if command_name == "pwd":
            current = str(Path.cwd())
            return {
                "success": True,
                "message": (
                    "commandsBridge is deprecated; migrate to "
                    "'qzx currentDir'. Current working directory: {}"
                ).format(current),
                "stdout": current,
                "deprecated": True,
                "replacement": "currentDir",
                "supported_through": "QZX 0.2.x",
                "details": {
                    "directory": current,
                    "deprecated": True,
                    "replacement": "currentDir",
                },
            }

        if command_name in {"cd", "clear", "exit"}:
            replacement_message, replacement_command = {
                "cd": (
                    "Use the QZX interactive terminal's built-in cd action.",
                    "terminal",
                ),
                "clear": ("Use 'qzx clearScreen'.", "clearScreen"),
                "exit": (
                    "Exit the calling shell or QZX interactive terminal.",
                    "terminal",
                ),
            }[command_name]
            return {
                "success": False,
                "error_code": "legacy_action_removed",
                "error": (
                    "The simulated '{}' action is not a native read-only "
                    "diagnostic."
                ).format(command_name),
                "message": replacement_message,
                "deprecated": True,
                "replacement": replacement_command,
                "supported_through": "QZX 0.2.x",
                "details": {
                    "deprecated": True,
                    "replacement": replacement_command,
                    "supported_through": "QZX 0.2.x",
                },
            }

        if command_name in self._LEGACY_BLOCKED_COMMANDS:
            return {
                "success": False,
                "error_code": "command_blocked",
                "error": (
                    "Command '{}' can mutate state or execute arbitrary "
                    "code."
                ).format(command_name),
                "message": (
                    "commandsBridge remains blocked for this operation and "
                    "is deprecated. Use a dedicated QZX command after "
                    "reviewing its safety contract."
                ),
                "deprecated": True,
                "supported_through": "QZX 0.2.x",
                "details": {
                    "deprecated": True,
                    "replacement_strategy": "dedicated_qzx_command",
                    "supported_through": "QZX 0.2.x",
                },
            }

        result = super().execute(command, *args)
        result["deprecated"] = True
        result["replacement"] = "runDiagnosticCommand"
        result["supported_through"] = "QZX 0.2.x"
        result["message"] = (
            "commandsBridge is deprecated; runDiagnosticCommand is its "
            "supported replacement. {}"
        ).format(
            result["message"],
        )
        return result
