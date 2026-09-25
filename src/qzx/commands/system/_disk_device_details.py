"""Per-disk inspection for listDiskDevices."""

from __future__ import annotations

import os
import subprocess

import psutil


def _usage(command, disk_path, result):
    try:
        if not os.path.exists(disk_path):
            return
        usage = psutil.disk_usage(disk_path)
        result.update(
            {
                "total": usage.total,
                "total_readable": command._format_bytes(usage.total),
                "used": usage.used,
                "used_readable": command._format_bytes(usage.used),
                "free": usage.free,
                "free_readable": command._format_bytes(usage.free),
                "percent": usage.percent,
            }
        )
    except Exception:
        pass


def _windows_details(disk_path, result):
    if ":" in disk_path:
        drive = os.path.splitdrive(disk_path)[0].replace(":", "")
        try:
            completed = subprocess.run(
                [
                    "wmic", "logicaldisk", "where", f"DeviceID='{drive}:'",
                    "get", "VolumeName,FileSystem,Size,FreeSpace",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            result["volume_info"] = completed.stdout.strip()
        except Exception:
            pass
        return
    try:
        completed = subprocess.run(
            [
                "wmic", "diskdrive", "where", f"DeviceID='{disk_path}'",
                "get", "Model,Size,MediaType,InterfaceType",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        result["disk_info"] = completed.stdout.strip()
    except Exception:
        pass


def _linux_details(disk_path, result):
    try:
        completed = subprocess.run(
            ["lsblk", "-o", "NAME,MODEL,SIZE,FSTYPE,MOUNTPOINT", disk_path],
            capture_output=True,
            text=True,
            check=False,
        )
        result["lsblk_info"] = completed.stdout.strip()
    except Exception:
        return
    try:
        completed = subprocess.run(
            ["hdparm", "-i", disk_path],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode == 0:
            result["hdparm_info"] = completed.stdout.strip()
    except Exception:
        pass


def _macos_details(disk_path, result):
    try:
        completed = subprocess.run(
            ["diskutil", "info", disk_path],
            capture_output=True,
            text=True,
            check=False,
        )
        result["diskutil_info"] = completed.stdout.strip()
    except Exception:
        pass


def get_disk_info(command, disk_path, os_type):
    """Return usage plus platform-specific detail for one disk path."""
    try:
        result = {"path": disk_path}
        _usage(command, disk_path, result)
        if os_type == "windows":
            _windows_details(disk_path, result)
        elif os_type == "linux":
            _linux_details(disk_path, result)
        elif os_type == "darwin":
            _macos_details(disk_path, result)
        return result
    except Exception:
        return None
