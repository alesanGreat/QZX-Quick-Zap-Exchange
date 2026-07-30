#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Inspect GPUs without shell execution or unstructured stdout."""

from __future__ import annotations

import json
import platform
import shutil
import subprocess

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
        detailed_value = self._parse_bool(detailed)
        if detailed_value is None:
            return {
                "success": False,
                "error_code": "invalid_detailed",
                "error": f"detailed must be true or false; got {detailed!r}.",
                "message": (
                    "Could not inspect GPUs because --detailed must be true "
                    "or false."
                ),
                "details": {"received": detailed},
            }

        warnings = []
        sources = []
        gpus = self._nvidia_gpus(detailed_value, warnings)
        if gpus:
            sources.append("nvidia-smi")

        platform_gpus, platform_source = self._platform_gpus(warnings)
        if platform_source:
            sources.append(platform_source)
        gpus = self._merge_gpus(gpus, platform_gpus)

        vendors = sorted(
            {gpu["vendor"] for gpu in gpus},
            key=str.casefold,
        )
        if gpus:
            vendor_summary = ", ".join(vendors)
            message = (
                f"Detected {len(gpus)} GPU"
                f"{'' if len(gpus) == 1 else 's'} from {vendor_summary}."
            )
        else:
            message = (
                f"No GPU was detected on {self._system_name}. "
                "The required platform inventory utility may be unavailable."
            )

        result = {
            "success": True,
            "message": message,
            "gpu_count": len(gpus),
            "detected_vendors": vendors,
            "gpus": gpus,
            "details": {
                "platform": self._system_name,
                "detailed": detailed_value,
                "sources": sources,
            },
        }
        if warnings:
            result["warnings"] = warnings
        return result

    def _nvidia_gpus(self, detailed, warnings):
        executable = self._path_lookup("nvidia-smi")
        if not executable:
            return []
        fields = ["name", "driver_version"]
        if detailed:
            fields.extend(
                [
                    "memory.total",
                    "memory.used",
                    "memory.free",
                    "utilization.gpu",
                    "temperature.gpu",
                ]
            )
        completed = self._run(
            [
                executable,
                f"--query-gpu={','.join(fields)}",
                "--format=csv,noheader,nounits",
            ],
            "nvidia-smi",
            warnings,
        )
        if completed is None:
            return []

        gpus = []
        for index, line in enumerate(completed.stdout.splitlines()):
            parts = [part.strip() for part in line.split(",")]
            if len(parts) != len(fields) or not parts[0]:
                warnings.append(
                    {
                        "code": "nvidia_row_unexpected",
                        "message": (
                            "nvidia-smi returned a row with an unexpected "
                            "number of fields."
                        ),
                    }
                )
                continue
            gpu = {
                "index": index,
                "name": parts[0],
                "vendor": "NVIDIA",
                "driver_version": parts[1],
                "source": "nvidia-smi",
            }
            if detailed:
                gpu["memory"] = {
                    "total_mib": self._number_or_text(parts[2]),
                    "used_mib": self._number_or_text(parts[3]),
                    "free_mib": self._number_or_text(parts[4]),
                }
                gpu["utilization_percent"] = self._number_or_text(parts[5])
                gpu["temperature_celsius"] = self._number_or_text(parts[6])
            gpus.append(gpu)
        return gpus

    def _platform_gpus(self, warnings):
        system = self._system_name.casefold()
        if system == "windows":
            return self._windows_gpus(warnings), "Win32_VideoController"
        if system == "linux":
            return self._linux_gpus(warnings), "lspci"
        if system == "darwin":
            return self._macos_gpus(warnings), "system_profiler"
        warnings.append(
            {
                "code": "unsupported_platform_inventory",
                "message": (
                    f"No generic GPU inventory provider is defined for "
                    f"{self._system_name}."
                ),
            }
        )
        return [], None

    def _windows_gpus(self, warnings):
        executable = self._path_lookup("powershell") or self._path_lookup(
            "pwsh"
        )
        if not executable:
            warnings.append(
                {
                    "code": "powershell_unavailable",
                    "message": (
                        "PowerShell was not found, so the Windows GPU "
                        "inventory could not be queried."
                    ),
                }
            )
            return []
        command = (
            "Get-CimInstance Win32_VideoController | "
            "Select-Object Name,AdapterCompatibility,AdapterRAM,"
            "DriverVersion,VideoProcessor | ConvertTo-Json -Compress"
        )
        completed = self._run(
            [executable, "-NoProfile", "-NonInteractive", "-Command", command],
            "Win32_VideoController",
            warnings,
        )
        if completed is None or not completed.stdout.strip():
            return []
        try:
            records = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            warnings.append(
                {
                    "code": "windows_gpu_json_invalid",
                    "message": (
                        "Windows returned invalid GPU inventory JSON: "
                        f"{exc.msg}."
                    ),
                }
            )
            return []
        if isinstance(records, dict):
            records = [records]
        if not isinstance(records, list):
            return []

        gpus = []
        for index, record in enumerate(records):
            if not isinstance(record, dict):
                continue
            name = str(record.get("Name") or "Unknown GPU")
            gpu = {
                "index": index,
                "name": name,
                "vendor": self._vendor(
                    name,
                    record.get("AdapterCompatibility"),
                ),
                "source": "Win32_VideoController",
            }
            if record.get("DriverVersion"):
                gpu["driver_version"] = str(record["DriverVersion"])
            if record.get("VideoProcessor"):
                gpu["processor"] = str(record["VideoProcessor"])
            adapter_ram = record.get("AdapterRAM")
            if isinstance(adapter_ram, (int, float)) and adapter_ram >= 0:
                gpu["memory"] = {
                    "total_bytes": int(adapter_ram),
                    "total_readable": self._format_bytes(adapter_ram),
                }
            gpus.append(gpu)
        return gpus

    def _linux_gpus(self, warnings):
        executable = self._path_lookup("lspci")
        if not executable:
            warnings.append(
                {
                    "code": "lspci_unavailable",
                    "message": (
                        "lspci was not found, so the Linux GPU inventory "
                        "could not be queried."
                    ),
                }
            )
            return []
        completed = self._run(
            [executable, "-D", "-nn"],
            "lspci",
            warnings,
        )
        if completed is None:
            return []
        markers = (
            "vga compatible controller",
            "3d controller",
            "display controller",
        )
        gpus = []
        for line in completed.stdout.splitlines():
            normalized = line.casefold()
            marker = next(
                (candidate for candidate in markers if candidate in normalized),
                None,
            )
            if marker is None:
                continue
            marker_end = normalized.index(marker) + len(marker)
            description = line[marker_end:].lstrip(" :").strip()
            gpus.append(
                {
                    "index": len(gpus),
                    "name": description or line.strip(),
                    "vendor": self._vendor(description),
                    "source": "lspci",
                    "raw": line.strip(),
                }
            )
        return gpus

    def _macos_gpus(self, warnings):
        executable = self._path_lookup("system_profiler")
        if not executable:
            warnings.append(
                {
                    "code": "system_profiler_unavailable",
                    "message": (
                        "system_profiler was not found, so the macOS GPU "
                        "inventory could not be queried."
                    ),
                }
            )
            return []
        completed = self._run(
            [executable, "SPDisplaysDataType", "-json"],
            "system_profiler",
            warnings,
        )
        if completed is None:
            return []
        try:
            document = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            warnings.append(
                {
                    "code": "macos_gpu_json_invalid",
                    "message": (
                        "macOS returned invalid GPU inventory JSON: "
                        f"{exc.msg}."
                    ),
                }
            )
            return []
        records = document.get("SPDisplaysDataType", [])
        if not isinstance(records, list):
            return []
        gpus = []
        for index, record in enumerate(records):
            if not isinstance(record, dict):
                continue
            name = str(record.get("_name") or "Unknown GPU")
            gpu = {
                "index": index,
                "name": name,
                "vendor": self._vendor(
                    name,
                    record.get("spdisplays_vendor"),
                ),
                "source": "system_profiler",
            }
            if record.get("spdisplays_vram"):
                gpu["memory"] = {
                    "reported": str(record["spdisplays_vram"])
                }
            if record.get("spdisplays_metal"):
                gpu["metal_support"] = str(record["spdisplays_metal"])
            gpus.append(gpu)
        return gpus

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
        merged = list(preferred)
        keys = {
            (gpu.get("vendor", "").casefold(), gpu.get("name", "").casefold())
            for gpu in merged
        }
        preferred_vendors = {
            gpu.get("vendor", "").casefold() for gpu in preferred
        }
        for gpu in additional:
            key = (
                gpu.get("vendor", "").casefold(),
                gpu.get("name", "").casefold(),
            )
            if key in keys:
                continue
            if (
                gpu.get("vendor", "").casefold() == "nvidia"
                and "nvidia" in preferred_vendors
            ):
                continue
            gpu = dict(gpu)
            gpu["index"] = len(merged)
            merged.append(gpu)
            keys.add(key)
        return merged

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
