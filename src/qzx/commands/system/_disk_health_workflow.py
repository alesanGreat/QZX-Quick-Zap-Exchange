"""Bounded smartctl orchestration for getDiskHealth."""

from __future__ import annotations

import json
import os
import re
import subprocess


def _validate_request(disk, view):
    disk_name = str(disk or "").strip()
    if not disk_name or not re.fullmatch(r"[A-Za-z0-9._:-]+", disk_name):
        return None, None, {
            "success": False,
            "error_code": "invalid_disk",
            "error": "Disk must be one identifier without path separators.",
            "message": (
                "Use a disk identifier such as sda, nvme0n1, disk0, or "
                "PhysicalDrive0."
            ),
            "disk": disk_name,
        }
    normalized_view = str(view or "").strip().lower()
    if normalized_view not in {"health", "full"}:
        return None, None, {
            "success": False,
            "error_code": "invalid_view",
            "error": "view must be 'health' or 'full'.",
            "message": "Choose the health summary or the full S.M.A.R.T. record.",
            "disk": disk_name,
            "view": view,
        }
    return disk_name, normalized_view, None


def _device_for_system(system, disk_name, view):
    if system == "windows":
        return rf"\\.\{disk_name}", None
    if system in {"linux", "darwin"}:
        return f"/dev/{disk_name}", None
    return None, {
        "success": False,
        "error_code": "unsupported_platform",
        "error": f"Unsupported operating system: {system}.",
        "message": (
            "getDiskHealth currently supports Windows, Linux, and macOS."
        ),
        "disk": disk_name,
        "view": view,
    }


def _missing_smartctl(disk_name, device, view):
    return {
        "success": False,
        "error_code": "smartctl_not_found",
        "error": "The smartctl executable is not available.",
        "message": (
            "Install smartmontools, verify smartctl is in PATH, and run the "
            "command again."
        ),
        "disk": disk_name,
        "device": device,
        "view": view,
    }


def _run_smartctl(command, executable, arguments, disk_name, device, view):
    try:
        return command._runner(
            [executable, *arguments],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=15.0,
            check=False,
            shell=False,
        ), None
    except subprocess.TimeoutExpired:
        return None, {
            "success": False,
            "error_code": "smartctl_timeout",
            "error": "smartctl did not finish within 15 seconds.",
            "message": (
                "The disk health query timed out; verify the device and "
                "smartmontools access before retrying."
            ),
            "disk": disk_name,
            "device": device,
            "view": view,
        }
    except OSError as exc:
        return None, {
            "success": False,
            "error_code": "smartctl_execution_failed",
            "error": f"{type(exc).__name__}: {exc}",
            "message": "QZX could not start the resolved smartctl executable.",
            "disk": disk_name,
            "device": device,
            "view": view,
        }


def _base_result(command, completed, disk_name, device, view, executable):
    flags = command._decode_status_flags(completed.returncode)
    return {
        "disk": disk_name,
        "device": device,
        "view": view,
        "smartctl_path": executable,
        "smartctl_return_code": completed.returncode,
        "smartctl_status_flags": flags,
        "stderr": (completed.stderr or "")[:65536],
        "warnings": [],
    }


def _query_failure(base, completed):
    return {
        **base,
        "success": False,
        "error_code": "smartctl_query_failed",
        "error": "smartctl could not complete a reliable device query.",
        "message": (
            "No reliable S.M.A.R.T. result was available for '{}'; review "
            "the structured status flags."
        ).format(base["device"]),
        "stdout": (completed.stdout or "")[:65536],
    }


def _full_result(base, completed):
    try:
        smart_data = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        return {
            **base,
            "success": False,
            "error_code": "invalid_smartctl_json",
            "error": f"JSONDecodeError: {exc}",
            "message": (
                "smartctl completed, but its full response was not valid JSON."
            ),
            "stdout": (completed.stdout or "")[:65536],
        }
    return {
        **base,
        "success": True,
        "message": (
            "Retrieved the full S.M.A.R.T. record for '{}'."
        ).format(base["device"]),
        "smart_data": smart_data,
    }


def _health_result(command, base, completed):
    output = (completed.stdout or "")[:65536]
    health = command._health_from_output(
        output, base["smartctl_status_flags"]
    )
    return {
        **base,
        "success": True,
        "message": f"S.M.A.R.T. health for '{base['device']}': {health}.",
        "health_status": health,
        "output": output,
    }


def execute_disk_health(command, disk, view="health"):
    """Run one exact smartctl binary with bounded time and no shell."""
    disk_name, normalized_view, error = _validate_request(disk, view)
    if error:
        return error
    system = command._system_name().lower()
    device, error = _device_for_system(system, disk_name, normalized_view)
    if error:
        return error
    smartctl = command._path_lookup("smartctl")
    if not smartctl:
        return _missing_smartctl(disk_name, device, normalized_view)
    executable = os.path.abspath(smartctl)
    arguments = (
        ["-H", device]
        if normalized_view == "health"
        else ["-a", "-j", device]
    )
    completed, error = _run_smartctl(
        command, executable, arguments, disk_name, device, normalized_view
    )
    if error:
        return error
    base = _base_result(
        command, completed, disk_name, device, normalized_view, executable
    )
    if completed.returncode & 0b111:
        return _query_failure(base, completed)
    if base["smartctl_status_flags"]:
        base["warnings"].append(
            {
                "code": "smartctl_status_flags",
                "message": "smartctl reported: {}.".format(
                    ", ".join(base["smartctl_status_flags"])
                ),
            }
        )
    if normalized_view == "full":
        return _full_result(base, completed)
    return _health_result(command, base, completed)
