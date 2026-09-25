"""Disk inventory orchestration for listDiskDevices."""

from __future__ import annotations

import json
import os
import platform
import plistlib
import subprocess

import psutil


def _append_partitions(command, result, os_type):
    for partition in psutil.disk_partitions(all=False):
        info = command._get_disk_info(partition.device, os_type)
        if info:
            result["disks"].append(info)


def _windows_physical_disks(result):
    try:
        completed = subprocess.run(
            [
                "wmic", "diskdrive", "get",
                "DeviceID,Model,Size,MediaType,InterfaceType",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        lines = completed.stdout.strip().split("\n")
        if len(lines) <= 1:
            return
        headers = lines[0].strip().split()
        result["physical_disks"] = []
        for line in lines[1:]:
            if not line.strip():
                continue
            values = line.strip().split(None, len(headers) - 1)
            result["physical_disks"].append(
                {
                    header.lower(): values[index]
                    for index, header in enumerate(headers)
                    if index < len(values)
                }
            )
    except Exception as exc:
        result["physical_disks_error"] = str(exc)


def _linux_block_devices(result):
    try:
        completed = subprocess.run(
            ["lsblk", "-o", "NAME,MODEL,SIZE,FSTYPE,MOUNTPOINT", "-J"],
            capture_output=True,
            text=True,
            check=False,
        )
        try:
            result["block_devices"] = json.loads(completed.stdout)
            return
        except json.JSONDecodeError:
            pass
        completed = subprocess.run(
            ["lsblk", "-o", "NAME,MODEL,SIZE,FSTYPE,MOUNTPOINT"],
            capture_output=True,
            text=True,
            check=False,
        )
        result["block_devices_raw"] = completed.stdout.strip()
    except Exception as exc:
        result["block_devices_error"] = str(exc)


def _macos_disk_list(result):
    try:
        completed = subprocess.run(
            ["diskutil", "list", "-plist"],
            capture_output=True,
            text=True,
            check=False,
        )
        try:
            result["disk_list"] = plistlib.loads(completed.stdout.encode("utf-8"))
            return
        except Exception:
            pass
        completed = subprocess.run(
            ["diskutil", "list"],
            capture_output=True,
            text=True,
            check=False,
        )
        result["disk_list_raw"] = completed.stdout.strip()
    except Exception as exc:
        result["disk_list_error"] = str(exc)


def _all_disks(command, result, os_type):
    if os_type == "windows":
        _append_partitions(command, result, os_type)
        _windows_physical_disks(result)
        return None
    if os_type == "linux":
        _linux_block_devices(result)
        _append_partitions(command, result, os_type)
        return None
    if os_type == "darwin":
        _macos_disk_list(result)
        _append_partitions(command, result, os_type)
        return None
    return {
        "success": False,
        "error_code": "unsupported_operating_system",
        "error": f"Unsupported operating system: {os_type}",
        "message": (
            "listDiskDevices currently supports Windows, Linux, and macOS."
        ),
    }


def _message(result, os_type, disk_path):
    logical_count = len(result["disks"])
    physical_count = len(result.get("physical_disks", []))
    if disk_path:
        return (
            f"Collected disk information for '{disk_path}'. "
            f"Found {logical_count} matching disk record(s)."
        )
    message = (
        f"Collected disk information on {os_type}: "
        f"{logical_count} mounted disk record(s)"
    )
    if physical_count:
        message += f" and {physical_count} physical disk record(s)"
    return message + "."


def execute_disk_devices(command, disk_path=None):
    """Run the public listDiskDevices workflow."""
    try:
        os_type = platform.system().lower()
        result = {"os_type": os_type, "disks": []}
        if disk_path:
            if not os.path.exists(disk_path):
                return {
                    "success": False,
                    "error_code": "disk_path_not_found",
                    "error": f"Disk path '{disk_path}' does not exist.",
                    "message": "Check the disk path and try again.",
                    "details": {"disk_path": os.path.abspath(disk_path)},
                }
            info = command._get_disk_info(disk_path, os_type)
            if info:
                result["disks"].append(info)
        else:
            error = _all_disks(command, result, os_type)
            if error:
                return error
        result["success"] = True
        result["message"] = _message(result, os_type, disk_path)
        return result
    except Exception as exc:
        return {
            "success": False,
            "error_code": "disk_inspection_failed",
            "error": f"{type(exc).__name__}: {str(exc)}",
            "message": f"Could not collect disk information: {str(exc)}",
        }
