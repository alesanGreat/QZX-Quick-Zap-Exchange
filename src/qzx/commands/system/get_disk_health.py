"""Inspect S.M.A.R.T. disk health through a bounded smartctl invocation."""

from __future__ import annotations

import platform
import shutil
import subprocess

from qzx.commands.system._disk_health_workflow import execute_disk_health
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
        return execute_disk_health(self, disk, view)
