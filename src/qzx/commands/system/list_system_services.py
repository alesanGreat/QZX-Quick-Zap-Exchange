#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""List services through the real native manager of the running system."""

import json
import os
import platform
import re
import shutil
import subprocess

from qzx.core.command_base import CommandBase


class ListSystemServicesCommand(CommandBase):
    """Inspect active and stopped services through the native manager."""

    name = "listSystemServices"
    description = "Lists operating-system services and their running status"
    category = "system"

    parameters = [
        {
            "name": "status",
            "description": (
                "Filter by service status (running, stopped, all; "
                "defaults to all)"
            ),
            "required": False,
            "default": "all",
        }
    ]

    examples = [
        {
            "command": "qzx listSystemServices",
            "description": "List all system services",
        },
        {
            "command": "qzx listSystemServices running",
            "description": "List only active running system services",
        },
    ]

    def execute(self, status="all"):
        status_filter = str(status).strip().lower()
        if status_filter not in {"all", "running", "stopped"}:
            status_filter = "all"

        operating_system = platform.system().lower()
        collectors = {
            "windows": self._collect_windows_services,
            "linux": self._collect_linux_services,
            "darwin": self._collect_launchd_services,
            "freebsd": self._collect_freebsd_services,
            "openbsd": self._collect_openbsd_services,
            "sunos": self._collect_smf_services,
        }
        collector = collectors.get(operating_system)
        if collector is None:
            return {
                "success": False,
                "error_code": "unsupported_operating_system",
                "error": f"Unsupported operating system: {operating_system}",
                "message": (
                    "No native service collector is available for this "
                    "operating system."
                ),
                "details": {"operating_system": operating_system},
            }

        try:
            services, service_manager, errors = collector()
        except Exception as exc:
            return {
                "success": False,
                "error_code": "service_discovery_failed",
                "error": f"{type(exc).__name__}: {exc}",
                "message": (
                    f"Failed to list services through the native manager "
                    f"on {operating_system}."
                ),
                "details": {"operating_system": operating_system},
            }

        if status_filter != "all":
            services = [
                service
                for service in services
                if service["status"] == status_filter
            ]
        services.sort(key=lambda item: item["name"].lower())

        message_lines = [
            f"System Services Diagnostics (Filter: '{status_filter}'):",
            f"- Service manager: {service_manager}",
            f"- Services found: {len(services)}",
        ]
        if services:
            message_lines.append("")
            message_lines.append("Top Services:")
            for service in services[:10]:
                message_lines.append(
                    "  - [{}] {} ({})".format(
                        service["status"].upper(),
                        service["name"],
                        service["display_name"][:60],
                    )
                )
            if len(services) > 10:
                message_lines.append(
                    f"  ... and {len(services) - 10} more."
                )
        else:
            message_lines.append("- No matching services found.")

        return {
            "success": True,
            "operating_system": operating_system,
            "service_manager": service_manager,
            "status_filter": status_filter,
            "total_services": len(services),
            "services": services,
            "errors": errors,
            "message": "\n".join(message_lines),
        }

    @staticmethod
    def _run(command, timeout=10):
        return subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )

    def _collect_windows_services(self):
        errors = []
        powershell = shutil.which("powershell") or shutil.which("pwsh")
        if powershell:
            result = self._run(
                [
                    powershell,
                    "-NoProfile",
                    "-Command",
                    (
                        "Get-Service | Select-Object Name, DisplayName, "
                        "@{Name='Status';Expression={$_.Status.ToString()}} "
                        "| ConvertTo-Json -Compress"
                    ),
                ]
            )
            if result.returncode == 0 and result.stdout.strip():
                decoded = json.loads(result.stdout)
                items = decoded if isinstance(decoded, list) else [decoded]
                return [
                    {
                        "name": item.get("Name", "unknown"),
                        "display_name": item.get("DisplayName", ""),
                        "status": (
                            "running"
                            if str(item.get("Status", "")).lower()
                            == "running"
                            else "stopped"
                        ),
                    }
                    for item in items
                ], "Windows Service Control Manager (PowerShell)", errors
            errors.append(
                "PowerShell Get-Service failed: "
                + (result.stderr.strip() or "empty response")
            )

        service_control = shutil.which("sc.exe") or shutil.which("sc")
        if not service_control:
            raise FileNotFoundError("neither PowerShell nor sc.exe was found")
        result = self._run(
            [
                service_control,
                "query",
                "type=",
                "service",
                "state=",
                "all",
            ]
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "sc.exe query failed")
        return (
            self._parse_sc_query(result.stdout),
            "Windows Service Control Manager (sc.exe)",
            errors,
        )

    def _collect_linux_services(self):
        errors = []
        systemctl = shutil.which("systemctl")
        if systemctl:
            result = self._run(
                [
                    systemctl,
                    "list-units",
                    "--type=service",
                    "--all",
                    "--no-legend",
                    "--no-pager",
                ]
            )
            if result.returncode == 0:
                services = []
                for line in result.stdout.splitlines():
                    parts = line.strip().split(None, 4)
                    if len(parts) < 4:
                        continue
                    services.append(
                        {
                            "name": parts[0],
                            "display_name": (
                                parts[4] if len(parts) > 4 else parts[0]
                            ),
                            "status": (
                                "running"
                                if parts[2] == "active"
                                else "stopped"
                            ),
                        }
                    )
                if services:
                    return services, "systemd", errors
            errors.append(
                "systemctl did not return services: "
                + (result.stderr.strip() or f"exit {result.returncode}")
            )

        rc_status = shutil.which("rc-status")
        if rc_status:
            result = self._run([rc_status, "--all"])
            if result.returncode == 0:
                services = self._parse_openrc_status(result.stdout)
                if services:
                    return services, "OpenRC", errors
            errors.append(
                "rc-status did not return services: "
                + (result.stderr.strip() or f"exit {result.returncode}")
            )

        init_directory = "/etc/init.d"
        if not os.path.isdir(init_directory):
            raise RuntimeError("; ".join(errors) or "no service manager found")
        services = []
        for name in sorted(os.listdir(init_directory)):
            script = os.path.join(init_directory, name)
            if not os.path.isfile(script):
                continue
            result = self._run([script, "status"], timeout=3)
            services.append(
                {
                    "name": name,
                    "display_name": name,
                    "status": (
                        "running" if result.returncode == 0 else "stopped"
                    ),
                }
            )
        if not services:
            raise RuntimeError("; ".join(errors) or "no init scripts found")
        return services, "SysV/OpenRC init scripts", errors

    def _collect_launchd_services(self):
        launchctl = shutil.which("launchctl")
        if not launchctl:
            raise FileNotFoundError("launchctl was not found")
        result = self._run([launchctl, "list"])
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "launchctl list failed")
        services = []
        for line in result.stdout.splitlines()[1:]:
            parts = line.split(None, 2)
            if len(parts) != 3:
                continue
            services.append(
                {
                    "name": parts[2],
                    "display_name": parts[2],
                    "status": (
                        "running" if parts[0] != "-" else "stopped"
                    ),
                }
            )
        return services, "launchd", []

    def _collect_freebsd_services(self):
        service = shutil.which("service")
        if not service:
            raise FileNotFoundError("FreeBSD service utility was not found")
        result = self._run([service, "-l"])
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "service -l failed")
        services = []
        for name in result.stdout.split():
            status = self._run([service, name, "onestatus"], timeout=3)
            services.append(
                {
                    "name": name,
                    "display_name": name,
                    "status": (
                        "running" if status.returncode == 0 else "stopped"
                    ),
                }
            )
        return services, "FreeBSD rc.d", []

    def _collect_openbsd_services(self):
        rcctl = shutil.which("rcctl")
        if not rcctl:
            raise FileNotFoundError("OpenBSD rcctl was not found")
        all_result = self._run([rcctl, "ls", "all"])
        started_result = self._run([rcctl, "ls", "started"])
        if all_result.returncode != 0 or started_result.returncode != 0:
            raise RuntimeError(
                all_result.stderr.strip()
                or started_result.stderr.strip()
                or "rcctl query failed"
            )
        started = set(started_result.stdout.split())
        services = [
            {
                "name": name,
                "display_name": name,
                "status": "running" if name in started else "stopped",
            }
            for name in all_result.stdout.split()
        ]
        return services, "OpenBSD rc.d (rcctl)", []

    def _collect_smf_services(self):
        svcs = shutil.which("svcs")
        if not svcs:
            raise FileNotFoundError("Solaris svcs was not found")
        result = self._run([svcs, "-H", "-o", "state,fmri"])
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "svcs query failed")
        services = []
        for line in result.stdout.splitlines():
            parts = line.strip().split(None, 1)
            if len(parts) != 2:
                continue
            state, name = parts
            services.append(
                {
                    "name": name,
                    "display_name": name,
                    "status": (
                        "running"
                        if state.lower() in {"online", "degraded"}
                        else "stopped"
                    ),
                }
            )
        return services, "Solaris Service Management Facility (SMF)", []

    @staticmethod
    def _parse_openrc_status(stdout):
        services = []
        line_pattern = re.compile(
            r"^\s*([A-Za-z0-9_.@:+-]+)\s+\[\s*([A-Za-z]+)\s*\]"
        )
        for line in stdout.splitlines():
            match = line_pattern.match(line)
            if not match:
                continue
            name, state = match.groups()
            services.append(
                {
                    "name": name,
                    "display_name": name,
                    "status": (
                        "running"
                        if state.lower() in {"started", "starting"}
                        else "stopped"
                    ),
                }
            )
        return services

    @staticmethod
    def _parse_sc_query(stdout):
        services = []
        current_service = None
        for line in stdout.splitlines():
            line = line.strip()
            if line.startswith("SERVICE_NAME:"):
                current_service = line.split(":", 1)[1].strip()
            elif current_service and line.startswith("STATE"):
                state_text = line.split(":", 1)[1]
                services.append(
                    {
                        "name": current_service,
                        "display_name": current_service,
                        "status": (
                            "running"
                            if "RUNNING" in state_text
                            else "stopped"
                        ),
                    }
                )
                current_service = None
        return services
