#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""GetDiskSpace Command - Retrieves information about disk space usage."""

import os

import psutil

from qzx.core.command_base import CommandBase


class GetDiskSpaceCommand(CommandBase):
    """Command to get information about disk space usage."""

    name = "getDiskSpace"
    description = "Gets information about disk space usage"
    category = "system"
    _byte_units = ("B", "KB", "MB", "GB", "TB", "PB")

    parameters = [
        {
            "name": "path",
            "description": (
                "Path to get disk information from. If not provided, all disks "
                "will be shown"
            ),
            "required": False,
            "default": None,
        }
    ]

    examples = [
        {
            "command": "qzx getDiskSpace",
            "description": "Get information about all available disks",
        },
        {
            "command": "qzx getDiskSpace C:",
            "description": "Get information about the C: drive (Windows)",
        },
        {
            "command": "qzx getDiskSpace /home",
            "description": "Get information about the /home partition (Linux/Mac)",
        },
    ]

    def __init__(
        self,
        disk_usage_provider=None,
        disk_partitions_provider=None,
    ):
        """Allow deterministic providers without patching psutil at runtime."""
        self._disk_usage = disk_usage_provider or psutil.disk_usage
        self._disk_partitions = disk_partitions_provider or psutil.disk_partitions

    def execute(self, path=None):
        """Get disk information for one path or all visible partitions."""
        try:
            if path:
                return self._execute_path(path)
            return self._execute_all_disks()
        except Exception as exc:
            return self._error_result(exc)

    def _execute_path(self, path):
        if not os.path.exists(path):
            return {
                "success": False,
                "error": f"Path '{path}' does not exist",
                "message": (
                    f"Failed to get disk information: Path '{path}' does not exist."
                ),
            }

        disk_info = self._disk_info(path, self._disk_usage(path))
        message = (
            f"Disk information for '{path}': "
            f"{disk_info['used']} used of {disk_info['total']} total "
            f"({disk_info['percent']}% used), {disk_info['free']} free."
        )
        return {
            "success": True,
            "message": message,
            "disk_info": disk_info,
        }

    def _execute_all_disks(self):
        disks = self._collect_disks()
        summary = self._summarize(disks)
        return {
            "success": True,
            "message": self._all_disks_message(disks, summary),
            "summary": summary,
            "disks": disks,
        }

    def _collect_disks(self):
        disks = []
        for partition in self._disk_partitions(all=False):
            try:
                usage = self._disk_usage(partition.mountpoint)
            except (PermissionError, OSError):
                continue
            info = self._disk_info(partition.mountpoint, usage)
            info.update(
                {
                    "device": partition.device,
                    "mountpoint": partition.mountpoint,
                    "fstype": partition.fstype,
                }
            )
            info.pop("path")
            disks.append(info)
        return disks

    def _disk_info(self, path, usage):
        return {
            "path": path,
            "total_bytes": usage.total,
            "used_bytes": usage.used,
            "free_bytes": usage.free,
            "total": self._format_bytes(usage.total),
            "used": self._format_bytes(usage.used),
            "free": self._format_bytes(usage.free),
            "percent": usage.percent,
        }

    def _summarize(self, disks):
        total_space = sum(disk["total_bytes"] for disk in disks)
        used_space = sum(disk["used_bytes"] for disk in disks)
        free_space = sum(disk["free_bytes"] for disk in disks)
        percent = 0
        if total_space > 0:
            percent = round((used_space / total_space) * 100, 1)
        return {
            "total_disks": len(disks),
            "total_space": total_space,
            "total_space_readable": self._format_bytes(total_space),
            "used_space": used_space,
            "used_space_readable": self._format_bytes(used_space),
            "free_space": free_space,
            "free_space_readable": self._format_bytes(free_space),
            "percent_used": percent,
        }

    def _all_disks_message(self, disks, summary):
        count = summary["total_disks"]
        summary_message = (
            f"Found {count} disk{'s' if count != 1 else ''}. "
            f"Total storage: {summary['total_space_readable']}, "
            f"Used: {summary['used_space_readable']} "
            f"({summary['percent_used']}%), "
            f"Free: {summary['free_space_readable']}."
        )
        details = [self._disk_detail(disk) for disk in disks]
        if not details:
            return summary_message
        return f"{summary_message}\n\nDisk details:\n" + "\n".join(details)

    @staticmethod
    def _disk_detail(disk):
        return (
            f"{disk['device']} ({disk['mountpoint']}): "
            f"{disk['used']} used of {disk['total']} "
            f"({disk['percent']}% used), {disk['free']} free."
        )

    @staticmethod
    def _error_result(exc):
        message = str(exc)
        return {
            "success": False,
            "error": f"Error getting disk information: {message}",
            "message": f"Failed to retrieve disk information: {message}",
        }
