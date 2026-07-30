"""Inspect S.M.A.R.T. disk health through a bounded smartctl invocation."""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess

from qzx.core.command_base import CommandBase


_SMARTCTL_STATUS_FLAGS = {
    0: "command_line_parse_error",
    1: "device_open_or_identification_failed",
    2: "smart_command_or_checksum_failed",
    3: "disk_failing",
    4: "prefail_attribute_below_threshold",
    5: "old_age_attribute_below_threshold",
    6: "error_log_contains_records",
    7: "self_test_log_contains_errors",
}


class GetDiskHealthCommand(CommandBase):
    """Return health or full S.M.A.R.T. data for one explicit disk."""

    name = "getDiskHealth"
    description = (
        "Inspects one disk's S.M.A.R.T. health with smartctl and reports "
        "status flags without treating health warnings as command failures"
    )
    category = "system"

    parameters = [
        {
            "name": "disk",
            "description": (
                "Disk identifier without path separators "
                "(for example: sda, nvme0n1, disk0, or PhysicalDrive0)"
            ),
            "required": True,
            "type": "str",
        },
        {
            "name": "view",
            "description": (
                'Detail level: "health" for a summary or "full" for '
                "smartctl JSON"
            ),
            "required": False,
            "default": "health",
            "type": "str",
        },
    ]

    examples = [
        {
            "command": "qzx getDiskHealth sda",
            "description": "Inspect the S.M.A.R.T. health of /dev/sda",
        },
        {
            "command": "qzx getDiskHealth PhysicalDrive0 --view full",
            "description": (
                "Read full S.M.A.R.T. JSON for a Windows physical drive"
            ),
        },
    ]

    def __init__(
        self,
        system_name=platform.system,
        path_lookup=shutil.which,
        runner=subprocess.run,
    ):
        self._system_name = system_name
        self._path_lookup = path_lookup
        self._runner = runner

    @staticmethod
    def _decode_status_flags(return_code):
        return [
            label
            for bit, label in _SMARTCTL_STATUS_FLAGS.items()
            if return_code & (1 << bit)
        ]

    @staticmethod
    def _health_from_output(output, status_flags):
        upper_output = output.upper()
        if "FAILED" in upper_output or "disk_failing" in status_flags:
            return "FAILED"
        if "PASSED" in upper_output:
            return "PASSED"
        return "UNKNOWN"

    def execute(self, disk, view="health"):
        """Run one exact smartctl binary with bounded time and no shell."""
        disk_name = str(disk or "").strip()
        if not disk_name or not re.fullmatch(r"[A-Za-z0-9._:-]+", disk_name):
            return {
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
            return {
                "success": False,
                "error_code": "invalid_view",
                "error": "view must be 'health' or 'full'.",
                "message": (
                    "Choose the health summary or the full S.M.A.R.T. record."
                ),
                "disk": disk_name,
                "view": view,
            }

        system = self._system_name().lower()
        if system == "windows":
            device = r"\\.\{}".format(disk_name)
        elif system in {"linux", "darwin"}:
            device = "/dev/{}".format(disk_name)
        else:
            return {
                "success": False,
                "error_code": "unsupported_platform",
                "error": "Unsupported operating system: {}.".format(system),
                "message": (
                    "getDiskHealth currently supports Windows, Linux, and "
                    "macOS."
                ),
                "disk": disk_name,
                "view": normalized_view,
            }

        smartctl_path = self._path_lookup("smartctl")
        if not smartctl_path:
            return {
                "success": False,
                "error_code": "smartctl_not_found",
                "error": "The smartctl executable is not available.",
                "message": (
                    "Install smartmontools, verify smartctl is in PATH, and "
                    "run the command again."
                ),
                "disk": disk_name,
                "device": device,
                "view": normalized_view,
            }

        arguments = (
            ["-H", device]
            if normalized_view == "health"
            else ["-a", "-j", device]
        )
        resolved_smartctl = os.path.abspath(smartctl_path)
        try:
            completed = self._runner(
                [resolved_smartctl, *arguments],
                capture_output=True,
                text=True,
                errors="replace",
                timeout=15.0,
                check=False,
                shell=False,
            )
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error_code": "smartctl_timeout",
                "error": "smartctl did not finish within 15 seconds.",
                "message": (
                    "The disk health query timed out; verify the device and "
                    "smartmontools access before retrying."
                ),
                "disk": disk_name,
                "device": device,
                "view": normalized_view,
            }
        except OSError as exc:
            return {
                "success": False,
                "error_code": "smartctl_execution_failed",
                "error": "{}: {}".format(type(exc).__name__, exc),
                "message": (
                    "QZX could not start the resolved smartctl executable."
                ),
                "disk": disk_name,
                "device": device,
                "view": normalized_view,
            }

        status_flags = self._decode_status_flags(completed.returncode)
        base_result = {
            "disk": disk_name,
            "device": device,
            "view": normalized_view,
            "smartctl_path": resolved_smartctl,
            "smartctl_return_code": completed.returncode,
            "smartctl_status_flags": status_flags,
            "stderr": (completed.stderr or "")[:65536],
            "warnings": [],
        }
        if completed.returncode & 0b111:
            return {
                **base_result,
                "success": False,
                "error_code": "smartctl_query_failed",
                "error": (
                    "smartctl could not complete a reliable device query."
                ),
                "message": (
                    "No reliable S.M.A.R.T. result was available for '{}'; "
                    "review the structured status flags."
                ).format(device),
                "stdout": (completed.stdout or "")[:65536],
            }

        if status_flags:
            base_result["warnings"].append(
                {
                    "code": "smartctl_status_flags",
                    "message": (
                        "smartctl reported: {}."
                    ).format(", ".join(status_flags)),
                }
            )

        if normalized_view == "full":
            try:
                smart_data = json.loads(completed.stdout)
            except json.JSONDecodeError as exc:
                return {
                    **base_result,
                    "success": False,
                    "error_code": "invalid_smartctl_json",
                    "error": "JSONDecodeError: {}".format(exc),
                    "message": (
                        "smartctl completed, but its full response was not "
                        "valid JSON."
                    ),
                    "stdout": (completed.stdout or "")[:65536],
                }
            return {
                **base_result,
                "success": True,
                "message": (
                    "Retrieved the full S.M.A.R.T. record for '{}'."
                ).format(device),
                "smart_data": smart_data,
            }

        output = (completed.stdout or "")[:65536]
        health_status = self._health_from_output(output, status_flags)
        return {
            **base_result,
            "success": True,
            "message": (
                "S.M.A.R.T. health for '{}': {}."
            ).format(device, health_status),
            "health_status": health_status,
            "output": output,
        }
