#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Inspect GPUs without shell execution or unstructured stdout."""

from __future__ import annotations

import platform
import shutil
import subprocess

from qzx.commands.system._gpu_inventory_providers import (
    linux_gpus,
    macos_gpus,
    nvidia_gpus,
    windows_gpus,
)
from qzx.commands.system._gpu_inventory_workflow import (
    execute_gpu_info,
    merge_gpus,
    platform_gpus,
)
from qzx.core.command_base import CommandBase


class GetGpuInfoCommand(CommandBase):
    """Return normalized GPU inventory and optional live NVIDIA metrics."""

    name = "getGpuInfo"
    description = (
        "Inspects installed GPUs and reports normalized vendor, driver, "
        "memory, and available utilization details"
    )
    category = "system"

    parameters = [
        {
            "name": "detailed",
            "description": (
                "Request extended driver, memory, temperature, and "
                "utilization fields when the platform exposes them"
            ),
            "required": False,
            "default": False,
            "type": "bool",
        }
    ]

    examples = [
        {
            "command": "qzx getGpuInfo",
            "description": "List detected GPUs with normalized vendor names",
        },
        {
            "command": "qzx getGpuInfo --detailed",
            "description": (
                "Include available driver, memory, temperature, and "
                "utilization fields"
            ),
        },
    ]

    def __init__(self, runner=None, path_lookup=None, system_name=None):
        """Allow deterministic boundary fakes without runtime patching."""
        self._runner = runner or subprocess.run
        self._path_lookup = path_lookup or shutil.which
        self._system_name = system_name or platform.system()

    def execute(self, detailed=False):
        """Inspect the current platform and return one stable result."""
        return execute_gpu_info(self, detailed)

    def _nvidia_gpus(self, detailed, warnings):
        return nvidia_gpus(self, detailed, warnings)

    def _platform_gpus(self, warnings):
        return platform_gpus(self, warnings)

    def _windows_gpus(self, warnings):
        return windows_gpus(self, warnings)

    def _linux_gpus(self, warnings):
        return linux_gpus(self, warnings)

    def _macos_gpus(self, warnings):
        return macos_gpus(self, warnings)

    def _run(self, arguments, source, warnings):
        try:
            completed = self._runner(
                arguments,
                capture_output=True,
                text=True,
                check=False,
                timeout=15,
                errors="replace",
            )
        except (OSError, subprocess.SubprocessError) as exc:
            warnings.append(
                {
                    "code": "gpu_provider_failed",
                    "message": (
                        f"{source} could not run: "
                        f"{type(exc).__name__}: {exc}."
                    ),
                }
            )
            return None
        if completed.returncode != 0:
            error = (completed.stderr or "").strip()
            warnings.append(
                {
                    "code": "gpu_provider_nonzero_exit",
                    "message": (
                        f"{source} exited with code {completed.returncode}"
                        f"{': ' + error[:300] if error else '.'}"
                    ),
                }
            )
            return None
        return completed

    @classmethod
    def _merge_gpus(cls, preferred, additional):
        return merge_gpus(preferred, additional)

    @staticmethod
    def _vendor(*values):
        text = " ".join(str(value or "") for value in values).casefold()
        for needle, vendor in (
            ("nvidia", "NVIDIA"),
            ("advanced micro devices", "AMD"),
            ("amd", "AMD"),
            ("radeon", "AMD"),
            ("intel", "Intel"),
            ("apple", "Apple"),
        ):
            if needle in text:
                return vendor
        return "Unknown"

    @staticmethod
    def _number_or_text(value):
        stripped = str(value).strip()
        try:
            return int(stripped)
        except ValueError:
            try:
                return float(stripped)
            except ValueError:
                return stripped

    @staticmethod
    def _format_bytes(value):
        amount = float(value)
        for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
            if amount < 1024 or unit == "TiB":
                return f"{amount:.2f} {unit}"
            amount /= 1024
        return f"{amount:.2f} TiB"
