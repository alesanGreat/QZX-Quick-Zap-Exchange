"""Platform GPU providers used by getGpuInfo."""

from __future__ import annotations

import json


def _warning(warnings, code, message):
    warnings.append({"code": code, "message": message})


def _nvidia_fields(detailed):
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
    return fields


def _nvidia_row(command, parts, index, detailed):
    gpu = {
        "index": index,
        "name": parts[0],
        "vendor": "NVIDIA",
        "driver_version": parts[1],
        "source": "nvidia-smi",
    }
    if detailed:
        gpu["memory"] = {
            "total_mib": command._number_or_text(parts[2]),
            "used_mib": command._number_or_text(parts[3]),
            "free_mib": command._number_or_text(parts[4]),
        }
        gpu["utilization_percent"] = command._number_or_text(parts[5])
        gpu["temperature_celsius"] = command._number_or_text(parts[6])
    return gpu


def nvidia_gpus(command, detailed, warnings):
    executable = command._path_lookup("nvidia-smi")
    if not executable:
        return []
    fields = _nvidia_fields(detailed)
    completed = command._run(
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
            _warning(
                warnings,
                "nvidia_row_unexpected",
                "nvidia-smi returned a row with an unexpected number of fields.",
            )
            continue
        gpus.append(_nvidia_row(command, parts, index, detailed))
    return gpus


def _windows_records(stdout, warnings):
    try:
        records = json.loads(stdout)
    except json.JSONDecodeError as exc:
        _warning(
            warnings,
            "windows_gpu_json_invalid",
            f"Windows returned invalid GPU inventory JSON: {exc.msg}.",
        )
        return []
    if isinstance(records, dict):
        return [records]
    return records if isinstance(records, list) else []


def _windows_row(command, record, index):
    name = str(record.get("Name") or "Unknown GPU")
    gpu = {
        "index": index,
        "name": name,
        "vendor": command._vendor(name, record.get("AdapterCompatibility")),
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
            "total_readable": command._format_bytes(adapter_ram),
        }
    return gpu


def windows_gpus(command, warnings):
    executable = command._path_lookup("powershell") or command._path_lookup("pwsh")
    if not executable:
        _warning(
            warnings,
            "powershell_unavailable",
            "PowerShell was not found, so the Windows GPU inventory could not be queried.",
        )
        return []
    script = (
        "Get-CimInstance Win32_VideoController | "
        "Select-Object Name,AdapterCompatibility,AdapterRAM,"
        "DriverVersion,VideoProcessor | ConvertTo-Json -Compress"
    )
    completed = command._run(
        [executable, "-NoProfile", "-NonInteractive", "-Command", script],
        "Win32_VideoController",
        warnings,
    )
    if completed is None or not completed.stdout.strip():
        return []
    return [
        _windows_row(command, record, index)
        for index, record in enumerate(_windows_records(completed.stdout, warnings))
        if isinstance(record, dict)
    ]


def linux_gpus(command, warnings):
    executable = command._path_lookup("lspci")
    if not executable:
        _warning(
            warnings,
            "lspci_unavailable",
            "lspci was not found, so the Linux GPU inventory could not be queried.",
        )
        return []
    completed = command._run([executable, "-D", "-nn"], "lspci", warnings)
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
        marker = next((item for item in markers if item in normalized), None)
        if marker is None:
            continue
        end = normalized.index(marker) + len(marker)
        description = line[end:].lstrip(" :").strip()
        gpus.append(
            {
                "index": len(gpus),
                "name": description or line.strip(),
                "vendor": command._vendor(description),
                "source": "lspci",
                "raw": line.strip(),
            }
        )
    return gpus


def _macos_records(stdout, warnings):
    try:
        document = json.loads(stdout)
    except json.JSONDecodeError as exc:
        _warning(
            warnings,
            "macos_gpu_json_invalid",
            f"macOS returned invalid GPU inventory JSON: {exc.msg}.",
        )
        return []
    records = document.get("SPDisplaysDataType", [])
    return records if isinstance(records, list) else []


def _macos_row(command, record, index):
    name = str(record.get("_name") or "Unknown GPU")
    gpu = {
        "index": index,
        "name": name,
        "vendor": command._vendor(name, record.get("spdisplays_vendor")),
        "source": "system_profiler",
    }
    if record.get("spdisplays_vram"):
        gpu["memory"] = {"reported": str(record["spdisplays_vram"])}
    if record.get("spdisplays_metal"):
        gpu["metal_support"] = str(record["spdisplays_metal"])
    return gpu


def macos_gpus(command, warnings):
    executable = command._path_lookup("system_profiler")
    if not executable:
        _warning(
            warnings,
            "system_profiler_unavailable",
            "system_profiler was not found, so the macOS GPU inventory could not be queried.",
        )
        return []
    completed = command._run(
        [executable, "SPDisplaysDataType", "-json"],
        "system_profiler",
        warnings,
    )
    if completed is None:
        return []
    return [
        _macos_row(command, record, index)
        for index, record in enumerate(_macos_records(completed.stdout, warnings))
        if isinstance(record, dict)
    ]
