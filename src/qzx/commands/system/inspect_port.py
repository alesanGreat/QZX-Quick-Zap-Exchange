#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
InspectPort Command - Checks if a port is in use, details the process using it, and can optionally terminate it.
"""

import os
import sys
import platform
import subprocess
import locale
import socket
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from qzx.core.command_base import CommandBase

class InspectPortCommand(CommandBase):
    """
    Command to inspect details of a specific port, identifying the process using it, and optionally killing it.
    """
    
    name = "inspectPort"
    description = "Checks if a port is in use, lists details of the process using it, and can optionally terminate it"
    category = "system"
    requires_explicit_approval = True
    approval_when_parameter = "kill"
    protected_process_names = {
        "csrss.exe",
        "idle",
        "lsass.exe",
        "registry",
        "services.exe",
        "smss.exe",
        "system",
        "wininit.exe",
        "winlogon.exe",
    }
    
    parameters = [
        {
            'name': 'port',
            'description': 'Port number to inspect',
            'required': True,
            'type': 'int'
        },
        {
            'name': 'kill',
            'description': 'Whether to terminate the process utilizing this port (true/false)',
            'required': False,
            'default': False,
            'type': 'bool'
        },
        {
            'name': 'expected_pid',
            'description': (
                'Exact PID previously observed on the port; required when '
                'kill is true to prevent terminating a different process'
            ),
            'required': False,
            'type': 'int'
        }
    ]
    
    examples = [
        {
            'command': 'qzx inspectPort 3000',
            'description': 'Check what is listening on port 3000'
        },
        {
            'command': 'qzx inspectPort 3000 true 12345 --yolo',
            'description': (
                'Terminate only PID 12345 when it is still the observed '
                'listener and no restorable filesystem target exists'
            )
        }
    ]

    @staticmethod
    def _system_name():
        """Return the host operating-system family."""
        return platform.system()
    
    def execute(self, port, kill=False, expected_pid=None):
        """
        Inspects the specified port
        
        Args:
            port (int/str): Port to inspect
            kill (str/bool, optional): Whether to terminate the process using it
            
        Returns:
            Dictionary containing port and process details
        """
        # Parse port
        try:
            port_num = int(port)
        except (TypeError, ValueError):
            return {
                "success": False,
                "error_code": "invalid_port",
                "error": f"Port must be an integer, received '{port}'",
                "message": f"Failed to inspect port: Port must be an integer, received '{port}'"
            }
        if not 1 <= port_num <= 65535:
            return {
                "success": False,
                "error_code": "invalid_port",
                "error": f"Port must be between 1 and 65535, received '{port_num}'",
                "message": (
                    "Failed to inspect port: Port must be between 1 and "
                    f"65535, received '{port_num}'."
                ),
            }
            
        # Parse kill flag without silently downgrading invalid mutation intent.
        kill_process = self._parse_bool(kill)
        if kill_process is None:
            return {
                "success": False,
                "error_code": "invalid_kill",
                "error": f"kill must be a boolean value, received '{kill}'.",
                "remediation": "Pass true to request termination or false to inspect.",
                "message": (
                    "Port inspection did not start because kill must be true "
                    "or false."
                ),
            }

        parsed_expected_pid = None
        if expected_pid not in (None, ""):
            try:
                parsed_expected_pid = int(expected_pid)
            except (TypeError, ValueError):
                return {
                    "success": False,
                    "error_code": "invalid_expected_pid",
                    "error": (
                        "expected_pid must be a positive integer, received "
                        f"'{expected_pid}'"
                    ),
                    "message": (
                        "Failed to inspect port: expected_pid must be a "
                        "positive integer."
                    ),
                }
            if parsed_expected_pid <= 0:
                return {
                    "success": False,
                    "error_code": "invalid_expected_pid",
                    "error": "expected_pid must be a positive integer.",
                    "message": (
                        "Failed to inspect port: expected_pid must be a "
                        "positive integer."
                    ),
                }
            
        try:
            import psutil
        except ImportError:
            return self._execute_fallback(
                port_num,
                kill_process,
                parsed_expected_pid,
            )

        # psutil.net_connections can abort the entire interpreter on SunOS,
        # which cannot be recovered with try/except. Use the command-line
        # fallback there so inspectPort returns a structured result.
        if self._system_name().lower() == "sunos":
            return self._execute_fallback(
                port_num,
                kill_process,
                parsed_expected_pid,
            )
            
        try:
            # Look for active connections on the target port
            matching_conns = []
            try:
                conns = psutil.net_connections(kind='inet')
            except (psutil.AccessDenied, Exception):
                # Fallback if net_connections requires admin
                return self._execute_fallback(
                    port_num,
                    kill_process,
                    parsed_expected_pid,
                )
                
            for conn in conns:
                if (
                    conn.laddr
                    and conn.laddr.port == port_num
                    and self._is_bound_socket(conn, psutil)
                ):
                    matching_conns.append(conn)
                    
            if not matching_conns:
                return {
                    "success": True,
                    "port": port_num,
                    "in_use": False,
                    "killed": False,
                    "message": f"Port {port_num} is free."
                }
                
            # Gather details of the process(es) using the port
            processes_info = []
            killed_pids = []
            errors = []
            
            # Use a set to avoid querying/killing the same PID multiple times
            pids = {conn.pid for conn in matching_conns if conn.pid is not None}

            if not pids:
                return {
                    "success": True,
                    "port": port_num,
                    "in_use": True,
                    "killed": False,
                    "processes": [],
                    "limitations": [
                        "The operating system did not expose an owning PID."
                    ],
                    "message": (
                        f"Port {port_num} is in use, but the operating system "
                        "did not expose an owning PID."
                    ),
                }

            if kill_process:
                guard_failure = self._validate_kill_target(
                    port_num,
                    pids,
                    parsed_expected_pid,
                )
                if guard_failure is not None:
                    return guard_failure
                pids = {parsed_expected_pid}
            
            for pid in sorted(pids):
                proc_info = {
                    "pid": pid,
                    "name": "unknown",
                    "status": "unknown",
                    "exe": None,
                    "cmdline": [],
                    "username": "unknown",
                    "cpu_percent": 0.0,
                    "memory_usage": {}
                }

                proc = None
                process_created_at = None
                try:
                    proc = psutil.Process(pid)
                    process_created_at = proc.create_time()
                    proc_info["name"] = proc.name()
                    proc_info["status"] = proc.status()
                    
                    try:
                        proc_info["exe"] = proc.exe()
                        proc_info["cmdline"] = proc.cmdline()
                        proc_info["username"] = proc.username()
                    except (psutil.AccessDenied, psutil.NoSuchProcess):
                        pass
                        
                    try:
                        mem = proc.memory_info()
                        proc_info["memory_usage"] = {
                            "rss": mem.rss,
                            "rss_readable": self._format_bytes(mem.rss)
                        }
                    except (psutil.AccessDenied, psutil.NoSuchProcess):
                        pass
                        
                except psutil.NoSuchProcess:
                    continue
                except Exception as e:
                    errors.append(f"Error reading process {pid}: {str(e)}")
                    
                processes_info.append(proc_info)

                # Perform termination if requested
                if kill_process:
                    protected_reason = self._protected_process_reason(
                        pid,
                        proc_info["name"],
                    )
                    if protected_reason is not None:
                        errors.append(protected_reason)
                        continue
                    if proc is None or process_created_at is None:
                        errors.append(
                            f"PID {pid} could not be verified before termination."
                        )
                        continue
                    try:
                        if (
                            not proc.is_running()
                            or proc.create_time() != process_created_at
                        ):
                            errors.append(
                                f"PID {pid} changed or exited before termination."
                            )
                            continue
                        proc.terminate()
                        try:
                            proc.wait(timeout=3)
                            proc_info["termination_method"] = "terminate"
                        except psutil.TimeoutExpired:
                            proc.kill()
                            proc.wait(timeout=2)
                            proc_info["termination_method"] = "forced_kill"
                        killed_pids.append(pid)
                    except psutil.NoSuchProcess:
                        errors.append(
                            f"PID {pid} exited before QZX could terminate it."
                        )
                    except psutil.AccessDenied:
                        errors.append(f"Access denied trying to terminate PID {pid}. Try running as Administrator.")
                    except psutil.TimeoutExpired:
                        errors.append(
                            f"PID {pid} did not exit within 5 seconds after termination."
                        )
                    except Exception as e:
                        errors.append(f"Failed to terminate PID {pid}: {str(e)}")
                        
            # Build message
            in_use_pids_str = ", ".join(str(p) for p in pids)
            proc_names_str = ", ".join(p["name"] for p in processes_info)
            
            if kill_process:
                if len(killed_pids) == len(pids):
                    remaining_pids = None
                    port_cleared = None
                    try:
                        remaining_connections = [
                            conn
                            for conn in psutil.net_connections(kind="inet")
                            if (
                                conn.laddr
                                and conn.laddr.port == port_num
                                and self._is_bound_socket(conn, psutil)
                            )
                        ]
                        remaining_pids = sorted(
                            {
                                conn.pid
                                for conn in remaining_connections
                                if conn.pid is not None
                            }
                        )
                        port_cleared = not remaining_connections
                    except (psutil.AccessDenied, Exception):
                        pass

                    if port_cleared is True:
                        success_msg = (
                            f"Terminated {proc_names_str} (PIDs: "
                            f"{in_use_pids_str}) and verified that port "
                            f"{port_num} is clear."
                        )
                    elif port_cleared is False:
                        success_msg = (
                            f"Terminated {proc_names_str} (PIDs: "
                            f"{in_use_pids_str}), but port {port_num} still "
                            f"has listener PID(s) {remaining_pids}."
                        )
                    else:
                        success_msg = (
                            f"Terminated {proc_names_str} (PIDs: "
                            f"{in_use_pids_str}). Re-inspect port {port_num} "
                            "because ownership verification was unavailable."
                        )
                    return {
                        "success": True,
                        "port": port_num,
                        "in_use": True,
                        "killed": True,
                        "killed_pids": killed_pids,
                        "port_cleared": port_cleared,
                        "remaining_pids": remaining_pids,
                        "processes": processes_info,
                        "errors": errors,
                        "message": success_msg
                    }
                else:
                    partial_msg = f"Failed to clear all processes on port {port_num}. Terminated PIDs: {killed_pids}. Errors: {'; '.join(errors)}"
                    return {
                        "success": False,
                        "port": port_num,
                        "in_use": True,
                        "killed": len(killed_pids) > 0,
                        "killed_pids": killed_pids,
                        "processes": processes_info,
                        "errors": errors,
                        "message": partial_msg
                    }
            else:
                msg = f"Port {port_num} is in use by: {proc_names_str} (PIDs: {in_use_pids_str})."
                return {
                    "success": True,
                    "port": port_num,
                    "in_use": True,
                    "killed": False,
                    "processes": processes_info,
                    "errors": errors,
                    "message": msg
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"An error occurred while inspecting port {port_num}: {str(e)}"
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
    def _validate_kill_target(port_num, observed_pids, expected_pid):
        """Require a caller-confirmed PID and fail closed on ownership drift."""
        observed = sorted(observed_pids)
        if expected_pid is None:
            return {
                "success": False,
                "error_code": "expected_pid_required",
                "port": port_num,
                "in_use": True,
                "killed": False,
                "observed_pids": observed,
                "error": (
                    "Terminating by port alone is unsafe because ownership can "
                    "change between inspection and termination."
                ),
                "details": {
                    "remediation": (
                        "Inspect the port without kill, then repeat with "
                        "kill=true and the exact observed PID."
                    )
                },
                "message": (
                    f"Port {port_num} is owned by PID(s) {observed}. No process "
                    "was terminated: provide expected_pid explicitly after "
                    "reviewing the listener."
                ),
            }
        if expected_pid not in observed_pids:
            return {
                "success": False,
                "error_code": "port_ownership_changed",
                "port": port_num,
                "in_use": True,
                "killed": False,
                "expected_pid": expected_pid,
                "observed_pids": observed,
                "error": (
                    f"Expected PID {expected_pid}, but the current listener "
                    f"owner is {observed}."
                ),
                "details": {
                    "remediation": (
                        "Review the new listener ownership before deciding "
                        "whether to retry."
                    )
                },
                "message": (
                    f"Port {port_num} ownership changed. Expected PID "
                    f"{expected_pid}; observed {observed}. No process was "
                    "terminated."
                ),
            }
        return None

    def _protected_process_reason(self, pid, process_name):
        """Block termination of QZX itself, its parent, and critical OS names."""
        normalized_name = str(process_name or "").strip().lower()
        if pid in {os.getpid(), os.getppid()}:
            return (
                f"Refusing to terminate PID {pid}: it is the QZX process or "
                "its invoking parent."
            )
        if normalized_name in self.protected_process_names:
            return (
                f"Refusing to terminate protected system process "
                f"'{process_name}' (PID {pid})."
            )
        return None

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
                    or "{} exited with code {}".format(
                        command[0],
                        result.returncode,
                    )
                )
                continue
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    try:
                        pids.add(int(line.strip()))
                    except ValueError:
                        continue
        return pids, not errors, errors

    def _execute_fallback(self, port_num, kill_process, expected_pid=None):
        """Fallback implementation using subprocess command line tools if psutil fails/lacks permission"""
        system_name = self._system_name().lower()
        is_windows = system_name == "windows"
        is_sunos = system_name == "sunos"
        pids = set()
        
        try:
            if is_windows:
                # Run netstat -ano
                res = self._subprocess_text(["netstat", "-ano"])
                if res.returncode == 0:
                    for line in res.stdout.splitlines():
                        line = line.strip()
                        if not line:
                            continue
                        parts = line.split()
                        if len(parts) < 4:
                            continue
                        protocol = parts[0].upper()
                        local_addr = parts[1]
                        if self._endpoint_port(local_addr) != port_num:
                            continue
                        if protocol == "TCP":
                            if len(parts) < 5 or parts[-2].upper() != "LISTENING":
                                continue
                        elif protocol != "UDP":
                            continue
                        try:
                            pids.add(int(parts[-1]))
                        except ValueError:
                            pass
            elif is_sunos:
                # netstat is part of SunOS and remains safe when psutil's
                # native system-wide connection enumeration is not.
                res = self._subprocess_text(
                    ["netstat", "-an", "-P", "tcp"]
                )
                if res.returncode != 0:
                    error = res.stderr.strip() or "netstat returned no diagnostics"
                    return {
                        "success": False,
                        "port": port_num,
                        "in_use": None,
                        "killed": False,
                        "error": error,
                        "message": (
                            f"Could not inspect port {port_num} with SunOS "
                            f"netstat: {error}"
                        )
                    }

                port_suffixes = (f".{port_num}", f":{port_num}")
                in_use = any(
                    len(parts) >= 2
                    and parts[-1].upper() in ("LISTEN", "LISTENING")
                    and parts[0].endswith(port_suffixes)
                    for line in res.stdout.splitlines()
                    if (parts := line.split())
                )

                if not in_use:
                    return {
                        "success": True,
                        "port": port_num,
                        "in_use": False,
                        "killed": False,
                        "message": f"Port {port_num} is free."
                    }

                limitation = (
                    "SunOS netstat confirms the listening port but does not "
                    "expose its owning PID in this mode."
                )
                if kill_process:
                    return {
                        "success": False,
                        "port": port_num,
                        "in_use": True,
                        "killed": False,
                        "processes": [],
                        "error": limitation,
                        "message": (
                            f"Port {port_num} is in use, but QZX cannot safely "
                            f"terminate its process: {limitation}"
                        )
                    }

                return {
                    "success": True,
                    "port": port_num,
                    "in_use": True,
                    "killed": False,
                    "processes": [],
                    "limitations": [limitation],
                    "message": (
                        f"Port {port_num} is in use. {limitation}"
                    )
                }
            else:
                # Linux/macOS fallback: listeners and bound UDP sockets only.
                pids, inspection_available, inspection_errors = (
                    self._lsof_listener_pids(port_num)
                )
                if not inspection_available:
                    error = "; ".join(inspection_errors)
                    return {
                        "success": False,
                        "port": port_num,
                        "in_use": None,
                        "killed": False,
                        "error": error,
                        "message": (
                            f"Could not inspect port {port_num} with lsof: "
                            f"{error}"
                        ),
                    }
                            
            if not pids:
                return {
                    "success": True,
                    "port": port_num,
                    "in_use": False,
                    "killed": False,
                    "message": f"Port {port_num} is free."
                }

            if kill_process:
                guard_failure = self._validate_kill_target(
                    port_num,
                    pids,
                    expected_pid,
                )
                if guard_failure is not None:
                    return guard_failure
                pids = {expected_pid}
                
            # If we need to kill the processes
            killed_pids = []
            errors = []
            processes_info = []
            
            for pid in sorted(pids):
                proc_name = "unknown"
                # Query process name using tasklist on Windows
                if is_windows:
                    proc_res = self._subprocess_text(
                        ["tasklist", "/NH", "/FI", f"PID eq {pid}"]
                    )
                    if proc_res.returncode == 0 and "No tasks" not in proc_res.stdout:
                        for line in proc_res.stdout.splitlines():
                            line_strip = line.strip()
                            if not line_strip or "Image Name" in line_strip or line_strip.startswith("==="):
                                continue
                            parts = line_strip.split()
                            if parts:
                                proc_name = parts[0]
                                break
                
                proc_info = {
                    "pid": pid,
                    "name": proc_name,
                    "status": "active"
                }
                processes_info.append(proc_info)
                
                if kill_process:
                    protected_reason = self._protected_process_reason(
                        pid,
                        proc_name,
                    )
                    if protected_reason is not None:
                        errors.append(protected_reason)
                        continue
                    if is_windows:
                        kill_res = self._subprocess_text(
                            ["taskkill", "/F", "/PID", str(pid)]
                        )
                        if kill_res.returncode == 0:
                            killed_pids.append(pid)
                        else:
                            errors.append(f"Failed to kill PID {pid}: {kill_res.stderr.strip()}")
                    else:
                        kill_res = self._subprocess_text(
                            ["kill", "-9", str(pid)]
                        )
                        if kill_res.returncode == 0:
                            killed_pids.append(pid)
                        else:
                            errors.append(f"Failed to kill PID {pid}: {kill_res.stderr.strip()}")
                            
            in_use_pids_str = ", ".join(str(p) for p in pids)
            proc_names_str = ", ".join(p["name"] for p in processes_info)
            
            if kill_process:
                if len(killed_pids) == len(pids):
                    port_cleared = None
                    remaining_pids = None
                    if not is_windows:
                        (
                            remaining,
                            verification_available,
                            _verification_errors,
                        ) = self._lsof_listener_pids(port_num)
                        if verification_available:
                            remaining_pids = sorted(remaining)
                            port_cleared = not remaining

                    if port_cleared is True:
                        message = (
                            f"Terminated selected processes: {proc_names_str} "
                            f"(PIDs: {in_use_pids_str}) and verified that port "
                            f"{port_num} is clear."
                        )
                    elif port_cleared is False:
                        message = (
                            f"Terminated selected processes: {proc_names_str} "
                            f"(PIDs: {in_use_pids_str}), but port {port_num} "
                            f"still has listener PID(s) {remaining_pids}."
                        )
                    else:
                        message = (
                            f"Terminated selected processes: {proc_names_str} "
                            f"(PIDs: {in_use_pids_str}). Re-inspect port "
                            f"{port_num} because fallback verification is "
                            "unavailable."
                        )
                    return {
                        "success": True,
                        "port": port_num,
                        "in_use": True,
                        "killed": True,
                        "killed_pids": killed_pids,
                        "port_cleared": port_cleared,
                        "remaining_pids": remaining_pids,
                        "processes": processes_info,
                        "message": message,
                    }
                else:
                    return {
                        "success": False,
                        "port": port_num,
                        "in_use": True,
                        "killed": len(killed_pids) > 0,
                        "killed_pids": killed_pids,
                        "processes": processes_info,
                        "errors": errors,
                        "message": f"Failed to clear all processes on port {port_num}. Errors: {'; '.join(errors)}"
                    }
            else:
                return {
                    "success": True,
                    "port": port_num,
                    "in_use": True,
                    "killed": False,
                    "processes": processes_info,
                    "message": f"Port {port_num} is in use by: {proc_names_str} (PIDs: {in_use_pids_str})."
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Fallback inspection failed for port {port_num}: {str(e)}"
            }
            
