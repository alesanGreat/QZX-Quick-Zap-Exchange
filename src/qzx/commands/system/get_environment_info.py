#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Compatibility command for the former all-in-one environment report."""

from qzx.core.command_base import CommandBase
from qzx.commands.system.system_info import SystemInfoCommand


class WonderMyEnvironmentCommand(CommandBase):
    """Delegate the legacy contract to ``systemInfo`` during migration."""

    name = "getEnvironmentInfo"
    aliases = ["WonderMyEnvironment", "environment", "sysinfo"]
    description = (
        "Compatibility interface for systemInfo; retained temporarily for "
        "0.2.x scripts"
    )
    category = "system"

    parameters = [
        {
            "name": "detailed",
            "description": (
                "Include RAM and storage details (true/false; defaults to true)"
            ),
            "required": False,
            "default": True,
            "type": "bool",
        }
    ]

    examples = [
        {
            "command": "qzx getEnvironmentInfo",
            "description": (
                "Get the legacy detailed report through systemInfo"
            ),
        },
        {
            "command": "qzx getEnvironmentInfo false",
            "description": "Get the legacy basic report through systemInfo",
        },
    ]

    def execute(self, detailed=True):
        """Return the replacement command's data without printing progress."""
        parsed_detailed = self._parse_bool(detailed)
        if parsed_detailed is None:
            return {
                "success": False,
                "error_code": "invalid_boolean",
                "error": f"Expected true/false, received {detailed!r}.",
                "message": (
                    "The 'detailed' value must be true or false. "
                    "Use 'qzx systemInfo --detailed' for the replacement."
                ),
                "details": {"replacement": "systemInfo"},
            }

        replacement_result = SystemInfoCommand().execute(
            detailed=parsed_detailed,
            include_environment=False,
        )
        if not replacement_result.get("success"):
            replacement_result["message"] = (
                "getEnvironmentInfo could not build its compatibility report. "
                + replacement_result["message"]
            )
            replacement_result["replacement"] = "systemInfo"
            return replacement_result

        migration = (
            "getEnvironmentInfo is deprecated and remains available throughout "
            "QZX 0.2.x. Migrate to 'qzx systemInfo{}'; it returns the same "
            "structured system report without automatic GPU probes."
        ).format(" --detailed" if parsed_detailed else "")
        return {
            "success": True,
            "message": migration + " " + replacement_result["message"],
            "output": replacement_result["message"],
            "system_info": replacement_result["system_info"],
            "details_requested": parsed_detailed,
            "environment_included": False,
            "warnings": replacement_result["warnings"],
            "deprecated": True,
            "replacement": "systemInfo",
            "supported_through": "QZX 0.2.x",
        }
