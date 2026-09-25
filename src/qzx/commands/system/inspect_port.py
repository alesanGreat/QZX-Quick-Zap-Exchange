#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""InspectPort Command - Reports which process owns a local port."""

from __future__ import annotations

import platform
from typing import ClassVar

from qzx.commands.system import _inspect_port_native as native
from qzx.commands.system import _inspect_port_psutil as psutil_support
from qzx.commands.system import _inspect_port_results as results
from qzx.core.command_base import CommandBase


class InspectPortCommand(CommandBase):
    """Inspect a bound local port without changing process state."""

    name = "inspectPort"
    description = (
        "Checks whether a local port is bound and reports the owning process "
        "without terminating it"
    )
    category = "system"

    result_schema: ClassVar[dict[str, object]] = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "message": {"type": "string"},
            "error": {"type": "string"},
            "error_code": {"type": "string"},
            "status": {"type": "string", "enum": ["free", "in_use"]},
            "port": {"type": "integer", "minimum": 1, "maximum": 65535},
            "in_use": {"type": ["boolean", "null"]},
            "observed_pids": {
                "type": "array",
                "items": {"type": "integer"},
            },
            "processes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": True,
                },
            },
            "limitations": {
                "type": "array",
                "items": {"type": "string"},
            },
            "errors": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "additionalProperties": True,
    }

    parameters = [
        {
            "name": "port",
            "description": "Port number to inspect",
            "required": True,
            "type": "int",
        }
    ]

    examples = [
        {
            "command": "qzx inspectPort 3000",
            "description": "Inspect the listener and obtain its PID and creation time",
        },
        {
            "command": "qzx inspectPort 5432 --json",
            "description": "Return the complete structured inspection result",
        },
    ]

    @staticmethod
    def _system_name():
        """Return the host operating-system family."""
        return platform.system()

    def execute(self, port):
        """Inspect a local port and report stable, structured ownership data."""
        port_num = self._parse_port(port)
        if isinstance(port_num, dict):
            return port_num

        try:
            import psutil
        except ImportError:
            return self._execute_fallback(port_num)

        system_name = self._system_name().lower()
        if system_name == "sunos":
            return self._execute_fallback(port_num)

        try:
            connections = psutil.net_connections(kind="inet")
        except Exception:
            return self._execute_fallback(port_num)

        matching = psutil_support.matching_connections(
            connections,
            port_num,
            psutil,
        )
        if not matching:
            if system_name == "darwin":
                return self._execute_fallback(port_num)
            return self._free_port_result(port_num)
        return self._result_from_connections(port_num, matching, psutil)

    def _result_from_connections(self, port_num, matching, psutil_module):
        pids = psutil_support.owner_pids(matching)
        if not pids:
            limitation = (
                "The operating system confirmed that the port is bound but "
                "did not expose an owning PID."
            )
            return self._occupied_result(port_num, [], [], [limitation])

        processes, errors = psutil_support.inspect_processes(
            pids,
            psutil_module,
            self._format_bytes,
        )
        return self._occupied_result(
            port_num,
            pids,
            processes,
            [],
            errors=errors,
        )

    @staticmethod
    def _parse_port(port):
        return results.parse_port(port)

    def _inspect_process(self, pid, psutil_module):
        return psutil_support.inspect_process(pid, psutil_module, self._format_bytes)

    @staticmethod
    def _occupied_result(
        port_num,
        pids,
        processes,
        limitations,
        *,
        errors=None,
    ):
        return results.occupied_result(
            port_num,
            pids,
            processes,
            limitations,
            errors=errors,
        )

    @staticmethod
    def _free_port_result(port_num):
        return results.free_port_result(port_num)

    @staticmethod
    def _is_bound_socket(connection, psutil_module):
        return psutil_support.is_bound_socket(connection, psutil_module)

    @staticmethod
    def _endpoint_port(endpoint):
        return native.endpoint_port(endpoint)

    @staticmethod
    def _subprocess_text(command):
        return native.subprocess_text(command)

    def _lsof_listener_pids(self, port_num):
        return native.lsof_listener_pids(port_num, self._subprocess_text)

    def _native_process_name(self, pid, is_windows):
        return native.native_process_name(pid, is_windows, self._subprocess_text)

    def _execute_fallback(self, port_num):
        """Inspect using native tools when psutil is unavailable or restricted."""
        system_name = self._system_name().lower()
        is_windows = system_name == "windows"
        return native.execute_fallback(
            port_num,
            system_name,
            self._subprocess_text,
            lambda pid: self._native_process_name(pid, is_windows),
        )

    @staticmethod
    def _fallback_failure(port_num, tool_name, result):
        return native.fallback_failure(port_num, tool_name, result)
