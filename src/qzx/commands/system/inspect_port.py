#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
InspectPort Command - Checks if a port is in use, details the process using it, and can optionally terminate it.
"""

import os
import sys
import platform
import subprocess
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
        }
    ]
    
    examples = [
        {
            'command': 'qzx inspectPort 3000',
            'description': 'Check what is listening on port 3000'
        },
        {
            'command': 'qzx inspectPort 3000 true --yolo',
            'description': 'Terminate the process when no restorable filesystem target exists'
        }
    ]
    
    def execute(self, port, kill=False):
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
        except ValueError:
            return {
                "success": False,
                "error": f"Port must be an integer, received '{port}'",
                "message": f"Failed to inspect port: Port must be an integer, received '{port}'"
            }
            
        # Parse kill flag
        if isinstance(kill, str):
            kill_process = kill.lower() in ('true', 'yes', 'y', '1', 't')
        else:
            kill_process = bool(kill)
            
        try:
            import psutil
        except ImportError:
            return self._execute_fallback(port_num, kill_process)

        # psutil.net_connections can abort the entire interpreter on SunOS,
        # which cannot be recovered with try/except. Use the command-line
        # fallback there so inspectPort returns a structured result.
        if platform.system().lower() == "sunos":
            return self._execute_fallback(port_num, kill_process)
            
        try:
            # Look for active connections on the target port
            matching_conns = []
            try:
                conns = psutil.net_connections(kind='inet')
            except (psutil.AccessDenied, Exception):
                # Fallback if net_connections requires admin
                return self._execute_fallback(port_num, kill_process)
                
            for conn in conns:
                if conn.laddr and conn.laddr.port == port_num:
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
            
            for pid in pids:
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
                
                try:
                    proc = psutil.Process(pid)
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
                    try:
                        proc = psutil.Process(pid)
                        proc.kill()  # Force kill
                        killed_pids.append(pid)
                    except psutil.NoSuchProcess:
                        killed_pids.append(pid)  # already gone
                    except psutil.AccessDenied:
                        errors.append(f"Access denied trying to terminate PID {pid}. Try running as Administrator.")
                    except Exception as e:
                        errors.append(f"Failed to terminate PID {pid}: {str(e)}")
                        
            # Build message
            in_use_pids_str = ", ".join(str(p) for p in pids)
            proc_names_str = ", ".join(p["name"] for p in processes_info)
            
            if kill_process:
                if len(killed_pids) == len(pids):
                    success_msg = f"Port {port_num} was cleared. Successfully terminated processes: {proc_names_str} (PIDs: {in_use_pids_str})."
                    return {
                        "success": True,
                        "port": port_num,
                        "in_use": True,
                        "killed": True,
                        "killed_pids": killed_pids,
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
            
    def _execute_fallback(self, port_num, kill_process):
        """Fallback implementation using subprocess command line tools if psutil fails/lacks permission"""
        system_name = platform.system().lower()
        is_windows = system_name == "windows"
        is_sunos = system_name == "sunos"
        pids = set()
        
        try:
            if is_windows:
                # Run netstat -ano
                res = subprocess.run(
                    ["netstat", "-ano"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False
                )
                if res.returncode == 0:
                    for line in res.stdout.splitlines():
                        line = line.strip()
                        if not line:
                            continue
                        # Look for lines containing target port, e.g. ":3000 "
                        parts = line.split()
                        if len(parts) >= 5:
                            local_addr = parts[1]
                            pid_str = parts[4]
                            if f":{port_num}" in local_addr:
                                try:
                                    pids.add(int(pid_str))
                                except ValueError:
                                    pass
            elif is_sunos:
                # netstat is part of SunOS and remains safe when psutil's
                # native system-wide connection enumeration is not.
                res = subprocess.run(
                    ["netstat", "-an", "-P", "tcp"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False
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
                # Linux/macOS fallback using lsof -t
                res = subprocess.run(
                    ["lsof", "-t", f"-i:{port_num}"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False
                )
                if res.returncode == 0:
                    for line in res.stdout.splitlines():
                        try:
                            pids.add(int(line.strip()))
                        except ValueError:
                            pass
                            
            if not pids:
                return {
                    "success": True,
                    "port": port_num,
                    "in_use": False,
                    "killed": False,
                    "message": f"Port {port_num} is free."
                }
                
            # If we need to kill the processes
            killed_pids = []
            errors = []
            processes_info = []
            
            for pid in pids:
                proc_name = "unknown"
                # Query process name using tasklist on Windows
                if is_windows:
                    proc_res = subprocess.run(
                        ["tasklist", "/NH", "/FI", f"PID eq {pid}"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        check=False
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
                    if is_windows:
                        kill_res = subprocess.run(
                            ["taskkill", "/F", "/PID", str(pid)],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True,
                            check=False
                        )
                        if kill_res.returncode == 0:
                            killed_pids.append(pid)
                        else:
                            errors.append(f"Failed to kill PID {pid}: {kill_res.stderr.strip()}")
                    else:
                        kill_res = subprocess.run(
                            ["kill", "-9", str(pid)],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True,
                            check=False
                        )
                        if kill_res.returncode == 0:
                            killed_pids.append(pid)
                        else:
                            errors.append(f"Failed to kill PID {pid}: {kill_res.stderr.strip()}")
                            
            in_use_pids_str = ", ".join(str(p) for p in pids)
            proc_names_str = ", ".join(p["name"] for p in processes_info)
            
            if kill_process:
                if len(killed_pids) == len(pids):
                    return {
                        "success": True,
                        "port": port_num,
                        "in_use": True,
                        "killed": True,
                        "killed_pids": killed_pids,
                        "processes": processes_info,
                        "message": f"Port {port_num} cleared. Terminated processes: {proc_names_str} (PIDs: {in_use_pids_str})."
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
            
