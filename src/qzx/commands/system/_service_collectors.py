"""Platform service collectors for listSystemServices."""

from __future__ import annotations

import json
import os
import shutil
import subprocess


def _powershell_services(command, executable, errors):
    script = (
        "Get-Service | Select-Object Name, DisplayName, "
        "@{Name='Status';Expression={$_.Status.ToString()}} "
        "| ConvertTo-Json -Compress"
    )
    try:
        result = command._command_runner(
            [executable, "-NoProfile", "-Command", script]
        )
    except subprocess.TimeoutExpired as exc:
        errors.append(
            f"PowerShell Get-Service timed out after {exc.timeout} seconds."
        )
        return None
    if result.returncode != 0 or not result.stdout.strip():
        errors.append(
            "PowerShell Get-Service failed: "
            + (result.stderr.strip() or "empty response")
        )
        return None
    try:
        decoded = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        errors.append(
            f"PowerShell Get-Service returned invalid JSON: {exc.msg}."
        )
        return None
    items = decoded if isinstance(decoded, list) else [decoded]
    if not all(isinstance(item, dict) for item in items):
        errors.append(
            "PowerShell Get-Service returned an unexpected JSON shape."
        )
        return None
    return [
        {
            "name": item.get("Name", "unknown"),
            "display_name": item.get("DisplayName", ""),
            "status": (
                "running"
                if str(item.get("Status", "")).lower() == "running"
                else "stopped"
            ),
        }
        for item in items
    ]


def _sc_services(command, errors):
    executable = (
        command._executable_finder("sc.exe")
        or command._executable_finder("sc")
    )
    if not executable:
        raise FileNotFoundError("neither PowerShell nor sc.exe was found")
    result = command._command_runner(
        [executable, "query", "type=", "service", "state=", "all"]
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "sc.exe query failed")
    return (
        command._parse_sc_query(result.stdout),
        "Windows Service Control Manager (sc.exe)",
        errors,
    )


def collect_windows_services(command):
    errors = []
    powershell = (
        command._executable_finder("powershell")
        or command._executable_finder("pwsh")
    )
    if powershell:
        services = _powershell_services(command, powershell, errors)
        if services is not None:
            return (
                services,
                "Windows Service Control Manager (PowerShell)",
                errors,
            )
    return _sc_services(command, errors)


def _systemd_services(command, executable, errors):
    result = command._run(
        [
            executable,
            "list-units",
            "--type=service",
            "--all",
            "--no-legend",
            "--no-pager",
        ]
    )
    if result.returncode != 0:
        errors.append(
            "systemctl did not return services: "
            + (result.stderr.strip() or f"exit {result.returncode}")
        )
        return None
    services = []
    for line in result.stdout.splitlines():
        parts = line.strip().split(None, 4)
        if len(parts) < 4:
            continue
        services.append(
            {
                "name": parts[0],
                "display_name": parts[4] if len(parts) > 4 else parts[0],
                "status": "running" if parts[2] == "active" else "stopped",
            }
        )
    return services or None


def _openrc_services(command, executable, errors):
    result = command._run([executable, "--all"])
    if result.returncode == 0:
        services = command._parse_openrc_status(result.stdout)
        if services:
            return services
    errors.append(
        "rc-status did not return services: "
        + (result.stderr.strip() or f"exit {result.returncode}")
    )
    return None


def _init_services(command, errors):
    directory = "/etc/init.d"
    if not os.path.isdir(directory):
        raise RuntimeError("; ".join(errors) or "no service manager found")
    services = []
    for name in sorted(os.listdir(directory)):
        script = os.path.join(directory, name)
        if not os.path.isfile(script) or not os.access(script, os.X_OK):
            continue
        result = command._run([script, "status"], timeout=3)
        services.append(
            {
                "name": name,
                "display_name": name,
                "status": "running" if result.returncode == 0 else "stopped",
            }
        )
    if not services:
        raise RuntimeError("; ".join(errors) or "no init scripts found")
    return services


def collect_linux_services(command):
    errors = []
    systemctl = shutil.which("systemctl")
    if systemctl:
        services = _systemd_services(command, systemctl, errors)
        if services:
            return services, "systemd", errors
    rc_status = shutil.which("rc-status")
    if rc_status:
        services = _openrc_services(command, rc_status, errors)
        if services:
            return services, "OpenRC", errors
    return _init_services(command, errors), "SysV/OpenRC init scripts", errors


def collect_launchd_services(command):
    executable = shutil.which("launchctl")
    if not executable:
        raise FileNotFoundError("launchctl was not found")
    result = command._run([executable, "list"])
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "launchctl list failed")
    services = []
    for line in result.stdout.splitlines()[1:]:
        parts = line.split(None, 2)
        if len(parts) == 3:
            services.append(
                {
                    "name": parts[2],
                    "display_name": parts[2],
                    "status": "running" if parts[0] != "-" else "stopped",
                }
            )
    return services, "launchd", []


def collect_freebsd_services(command):
    executable = shutil.which("service")
    if not executable:
        raise FileNotFoundError("FreeBSD service utility was not found")
    result = command._run([executable, "-l"])
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "service -l failed")
    services = []
    for name in result.stdout.split():
        status = command._run([executable, name, "onestatus"], timeout=3)
        services.append(
            {
                "name": name,
                "display_name": name,
                "status": "running" if status.returncode == 0 else "stopped",
            }
        )
    return services, "FreeBSD rc.d", []


def collect_openbsd_services(command):
    executable = shutil.which("rcctl")
    if not executable:
        raise FileNotFoundError("OpenBSD rcctl was not found")
    all_result = command._run([executable, "ls", "all"])
    started_result = command._run([executable, "ls", "started"])
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


def collect_smf_services(command):
    executable = shutil.which("svcs")
    if not executable:
        raise FileNotFoundError("Solaris svcs was not found")
    result = command._run([executable, "-H", "-o", "state,fmri"])
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
