#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""InspectPort Command - Reports which process owns a local port."""

import locale
import platform
import socket
import subprocess

from qzx.core.command_base import CommandBase


class InspectPortCommand(CommandBase):
    """Inspect a bound local port without changing process state."""

    name = "inspectPort"
    description = (
        "Checks whether a local port is bound and reports the owning process "
        "without terminating it"
    )
    category = "system"

    parameters = [
        {
            "name": "port",
            "description": "Port number to inspect",
            "required": True,
            "type": "int",
        },
        {
            "name": "kill",
            "description": (
                "Deprecated compatibility flag; true returns migration "
                "guidance and never terminates a process"
            ),
            "required": False,
            "default": False,
            "type": "bool",
        },
        {
            "name": "expected_pid",
            "description": (
                "Deprecated compatibility value used only to explain whether "
                "the previously observed PID still owns the port"
            ),
            "required": False,
            "default": None,
            "type": "int",
        },
    ]

    examples = [
        {
            "command": "qzx inspectPort 3000",
            "description": "Inspect the listener and obtain its PID and creation time",
        },
        {
            "command": (
                "qzx killProcess 12345 --expected-create-time "
                "1750000000.25 --yolo"
            ),
            "description": (
                "After reviewing inspectPort output, terminate that exact "
                "process with the dedicated command"
            ),
        },
    ]

    @staticmethod
    def _system_name():
        """Return the host operating-system family."""
        return platform.system()

    def execute(self, port, kill=False, expected_pid=None):
        """Inspect a local port and report stable, structured ownership data."""
        port_num = self._parse_port(port)
        if isinstance(port_num, dict):
            return port_num

        kill_requested = self._parse_bool(kill)
        if kill_requested is None:
            return {
                "success": False,
                "error_code": "invalid_kill",
                "error": f"kill must be a boolean value, received {kill!r}.",
                "remediation": (
                    "Pass false or omit the legacy flag. Use killProcess as a "
                    "separate, explicit action after inspecting the listener."
                ),
                "message": (
                    "Port inspection did not start because kill must be true "
                    "or false."
                ),
            }

        parsed_expected_pid = self._parse_expected_pid(expected_pid)
        if isinstance(parsed_expected_pid, dict):
            return parsed_expected_pid

        try:
            import psutil
        except ImportError:
            return self._execute_fallback(
                port_num,
                kill_requested,
                parsed_expected_pid,
            )

        system_name = self._system_name().lower()

        # On SunOS, psutil.net_connections can terminate the interpreter
        # instead of raising a recoverable exception.
        if system_name == "sunos":
            return self._execute_fallback(
                port_num,
                kill_requested,
                parsed_expected_pid,
            )

        try:
            connections = psutil.net_connections(kind="inet")
        except Exception:
            return self._execute_fallback(
                port_num,
                kill_requested,
                parsed_expected_pid,
            )

        matching = [
            connection
            for connection in connections
            if (
                connection.laddr
                and connection.laddr.port == port_num
                and self._is_bound_socket(connection, psutil)
            )
        ]
        if not matching:
            # macOS can omit otherwise visible listeners from psutil's
            # process-wide connection snapshot. Its native lsof query is
            # authoritative for this exact port and avoids a false "free".
            if system_name == "darwin":
                return self._execute_fallback(
                    port_num,
                    kill_requested,
                    parsed_expected_pid,
                )
            return self._free_port_result(port_num)

        pids = sorted(
            {
                connection.pid
                for connection in matching
                if connection.pid is not None
            }
        )
        limitations = []
        if not pids:
            limitations.append(
                "The operating system confirmed that the port is bound but "
                "did not expose an owning PID."
            )
            return self._occupied_result(
                port_num,
                [],
                [],
                limitations,
                kill_requested,
                parsed_expected_pid,
            )

        processes = []
        errors = []
        for pid in pids:
            process_info = self._inspect_process(pid, psutil)
            if process_info["success"]:
                processes.append(process_info["process"])
            else:
                errors.append(process_info["error"])
                processes.append(
                    {
                        "pid": pid,
                        "name": "unknown",
                        "status": "unknown",
                        "create_time": None,
                        "executable": None,
                        "command": [],
                        "username": None,
                        "memory": None,
                    }
                )

        return self._occupied_result(
            port_num,
            pids,
            processes,
            limitations,
            kill_requested,
            parsed_expected_pid,
            errors=errors,
        )

    @staticmethod
    def _parse_port(port):
        try:
            port_num = int(port)
        except (TypeError, ValueError):
            return {
                "success": False,
                "error_code": "invalid_port",
                "error": f"Port must be an integer, received {port!r}.",
                "message": (
                    f"Failed to inspect port: expected an integer, got {port!r}."
                ),
            }
        if not 1 <= port_num <= 65535:
            return {
                "success": False,
                "error_code": "invalid_port",
                "error": (
                    f"Port must be between 1 and 65535, received {port_num}."
                ),
                "message": (
                    "Failed to inspect port: port numbers range from 1 to "
                    f"65535, but {port_num} was requested."
                ),
            }
        return port_num

    @staticmethod
    def _parse_expected_pid(expected_pid):
        if expected_pid in (None, ""):
            return None
        try:
            parsed = int(expected_pid)
        except (TypeError, ValueError):
            return {
                "success": False,
                "error_code": "invalid_expected_pid",
                "error": (
                    "expected_pid must be a positive integer, received "
                    f"{expected_pid!r}."
                ),
                "message": (
                    "Port inspection did not start because expected_pid was "
                    "not a positive integer."
                ),
            }
        if parsed <= 0:
            return {
                "success": False,
                "error_code": "invalid_expected_pid",
                "error": "expected_pid must be a positive integer.",
                "message": (
                    "Port inspection did not start because expected_pid was "
                    "not a positive integer."
                ),
            }
        return parsed

    def _inspect_process(self, pid, psutil_module):
        try:
            process = psutil_module.Process(pid)
            process_info = {
                "pid": pid,
                "name": process.name(),
                "status": process.status(),
                "create_time": process.create_time(),
                "executable": None,
                "command": [],
                "username": None,
                "memory": None,
            }
            try:
                process_info["executable"] = process.exe()
                process_info["command"] = process.cmdline()
                process_info["username"] = process.username()
                memory = process.memory_info()
                process_info["memory"] = {
                    "rss_bytes": memory.rss,
                    "rss_formatted": self._format_bytes(memory.rss),
                }
            except (
                psutil_module.AccessDenied,
                psutil_module.NoSuchProcess,
                psutil_module.ZombieProcess,
            ):
                pass
            return {"success": True, "process": process_info}
        except psutil_module.NoSuchProcess:
            return {
                "success": False,
                "error": (
                    f"PID {pid} exited while QZX was collecting its details."
                ),
            }
        except psutil_module.AccessDenied:
            return {
                "success": False,
                "error": (
                    f"The operating system denied access to details for PID {pid}."
                ),
            }
        except Exception as exc:
            return {
                "success": False,
                "error": (
                    f"Could not inspect PID {pid}: {type(exc).__name__}: {exc}"
                ),
            }

    def _occupied_result(
        self,
        port_num,
        pids,
        processes,
        limitations,
        kill_requested,
        expected_pid,
        *,
        errors=None,
    ):
        observed_pids = sorted(pids)
        if kill_requested:
            return self._termination_moved_result(
                port_num,
                observed_pids,
                processes,
                limitations,
                expected_pid,
                errors or [],
            )

        names = [process["name"] for process in processes if process.get("name")]
        owner_summary = ", ".join(names) if names else "an owner not exposed by the OS"
        pid_summary = (
            ", ".join(str(pid) for pid in observed_pids)
            if observed_pids
            else "unavailable"
        )
        result = {
            "success": True,
            "status": "in_use",
            "port": port_num,
            "in_use": True,
            "killed": False,
            "observed_pids": observed_pids,
            "processes": processes,
            "limitations": limitations,
            "errors": errors or [],
            "message": (
                f"Port {port_num} is in use by {owner_summary} "
                f"(PID(s): {pid_summary}). No process state was changed."
            ),
        }
        return result

    @staticmethod
    def _termination_moved_result(
        port_num,
        observed_pids,
        processes,
        limitations,
        expected_pid,
        errors,
    ):
        suggestions = []
        for process in processes:
            pid = process.get("pid")
            create_time = process.get("create_time")
            if pid is None or create_time is None:
                continue
            command = (
                f"qzx killProcess {pid} "
                f"--expected-create-time {create_time} --yolo"
            )
            suggestions.append(command)

        ownership_changed = (
            expected_pid is not None and expected_pid not in observed_pids
        )
        if ownership_changed:
            ownership_note = (
                f"The legacy expected PID {expected_pid} no longer owns the "
                f"port; current PID(s): {observed_pids or 'unavailable'}."
            )
        elif observed_pids and not suggestions:
            ownership_note = (
                "QZX withheld a termination command because the operating "
                "system did not expose a process creation timestamp. "
                "Re-inspect until that identity fingerprint is available."
            )
        else:
            ownership_note = (
                "Review the listener details, then use the dedicated "
                "killProcess command if termination is still appropriate."
            )

        return {
            "success": False,
            "status": "read_only",
            "error_code": "operation_moved",
            "error": (
                "inspectPort is read-only; its legacy kill option no longer "
                "terminates processes."
            ),
            "port": port_num,
            "in_use": True,
            "killed": False,
            "expected_pid": expected_pid,
            "observed_pids": observed_pids,
            "processes": processes,
            "limitations": limitations,
            "errors": errors,
            "details": {
                "ownership_changed": ownership_changed,
                "remediation": ownership_note,
                "suggested_commands": suggestions,
            },
            "message": (
                "Port inspection completed safely and no process was "
                f"terminated. {ownership_note}"
            ),
        }

    @staticmethod
    def _free_port_result(port_num):
        return {
            "success": True,
            "status": "free",
            "port": port_num,
            "in_use": False,
            "killed": False,
            "observed_pids": [],
            "processes": [],
            "message": f"Port {port_num} is free.",
        }

    @staticmethod
    def _is_bound_socket(connection, psutil_module):
        """Accept TCP listeners and bound UDP sockets, not client connections."""
        if connection.type == socket.SOCK_DGRAM:
            return True
        return connection.status in {
            psutil_module.CONN_LISTEN,
            "LISTEN",
            "LISTENING",
        }

    @staticmethod
    def _endpoint_port(endpoint):
        """Extract an exact numeric port from netstat IPv4/IPv6 endpoints."""
        if not endpoint or ":" not in endpoint:
            return None
        candidate = endpoint.rsplit(":", 1)[-1]
        try:
            return int(candidate)
        except ValueError:
            return None

    @staticmethod
    def _subprocess_text(command):
        """Run a native diagnostic with the host encoding and bounded output."""
        return subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding=locale.getencoding(),
            errors="replace",
            timeout=20,
            check=False,
        )

    def _lsof_listener_pids(self, port_num):
        """Return listener PIDs and whether both TCP and UDP checks ran."""
        pids = set()
        errors = []
        commands = (
            [
                "lsof",
                "-nP",
                "-t",
                f"-iTCP:{port_num}",
                "-sTCP:LISTEN",
            ],
            ["lsof", "-nP", "-t", f"-iUDP:{port_num}"],
        )
        for command in commands:
            result = self._subprocess_text(command)
            if result.returncode not in (0, 1):
                errors.append(
                    result.stderr.strip()
                    or f"{command[0]} exited with code {result.returncode}"
                )
                continue
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    try:
                        pids.add(int(line.strip()))
                    except ValueError:
                        continue
        return pids, not errors, errors

    def _native_process_name(self, pid, is_windows):
        if is_windows:
            result = self._subprocess_text(
                ["tasklist", "/NH", "/FI", f"PID eq {pid}"]
            )
            if result.returncode == 0 and "No tasks" not in result.stdout:
                for line in result.stdout.splitlines():
                    stripped = line.strip()
                    if stripped and not stripped.startswith("="):
                        return stripped.split()[0]
        else:
            result = self._subprocess_text(
                ["ps", "-p", str(pid), "-o", "comm="]
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip().splitlines()[0]
        return "unknown"

    def _execute_fallback(
        self,
        port_num,
        kill_process=False,
        expected_pid=None,
    ):
        """Inspect using native tools when psutil is unavailable or restricted."""
        system_name = self._system_name().lower()
        is_windows = system_name == "windows"
        pids = set()

        try:
            if is_windows:
                result = self._subprocess_text(["netstat", "-ano"])
                if result.returncode != 0:
                    return self._fallback_failure(port_num, "netstat", result)
                for line in result.stdout.splitlines():
                    parts = line.strip().split()
                    if len(parts) < 4:
                        continue
                    protocol = parts[0].upper()
                    if self._endpoint_port(parts[1]) != port_num:
                        continue
                    if protocol == "TCP":
                        if len(parts) < 5 or parts[-2].upper() != "LISTENING":
                            continue
                    elif protocol != "UDP":
                        continue
                    try:
                        pids.add(int(parts[-1]))
                    except ValueError:
                        continue
            elif system_name == "sunos":
                result = self._subprocess_text(["netstat", "-an", "-P", "tcp"])
                if result.returncode != 0:
                    return self._fallback_failure(port_num, "SunOS netstat", result)
                suffixes = (f".{port_num}", f":{port_num}")
                in_use = any(
                    len(parts) >= 2
                    and parts[-1].upper() in {"LISTEN", "LISTENING"}
                    and parts[0].endswith(suffixes)
                    for line in result.stdout.splitlines()
                    if (parts := line.split())
                )
                if not in_use:
                    return self._free_port_result(port_num)
                limitation = (
                    "SunOS netstat confirms the listening port but does not "
                    "expose its owning PID in this mode."
                )
                return self._occupied_result(
                    port_num,
                    [],
                    [],
                    [limitation],
                    kill_process,
                    expected_pid,
                )
            else:
                pids, available, inspection_errors = self._lsof_listener_pids(
                    port_num
                )
                if not available:
                    return {
                        "success": False,
                        "error_code": "inspection_unavailable",
                        "error": "; ".join(inspection_errors),
                        "port": port_num,
                        "in_use": None,
                        "killed": False,
                        "message": (
                            f"Could not inspect port {port_num} with lsof: "
                            f"{'; '.join(inspection_errors)}"
                        ),
                    }

            if not pids:
                return self._free_port_result(port_num)

            processes = [
                {
                    "pid": pid,
                    "name": self._native_process_name(pid, is_windows),
                    "status": "active",
                    "create_time": None,
                    "executable": None,
                    "command": [],
                    "username": None,
                    "memory": None,
                }
                for pid in sorted(pids)
            ]
            limitations = [
                "Native fallback inspection could not obtain process creation "
                "timestamps; re-inspect with psutil before terminating a PID."
            ]
            return self._occupied_result(
                port_num,
                sorted(pids),
                processes,
                limitations,
                kill_process,
                expected_pid,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return {
                "success": False,
                "error_code": "inspection_failed",
                "error": f"{type(exc).__name__}: {exc}",
                "port": port_num,
                "in_use": None,
                "killed": False,
                "message": (
                    f"Native inspection failed for port {port_num}: "
                    f"{type(exc).__name__}: {exc}"
                ),
            }

    @staticmethod
    def _fallback_failure(port_num, tool_name, result):
        diagnostic = (
            result.stderr.strip()
            or result.stdout.strip()
            or f"exit code {result.returncode}"
        )
        return {
            "success": False,
            "error_code": "inspection_unavailable",
            "error": diagnostic,
            "port": port_num,
            "in_use": None,
            "killed": False,
            "message": (
                f"Could not inspect port {port_num} with {tool_name}: "
                f"{diagnostic}"
            ),
        }
