"""Detailed system collection and GPU formatting for TerminalWelcome."""

from __future__ import annotations

import platform


def collect_system_info(psutil_module):
    """Collect the explicitly requested detailed system snapshot."""
    info = {
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "architecture": platform.machine(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
    }
    if psutil_module is None:
        return info

    _collect_ram(psutil_module, info)
    _collect_disks(psutil_module, info)
    _collect_cpu(psutil_module, info)
    return info


def _collect_ram(psutil_module, info):
    try:
        memory = psutil_module.virtual_memory()
        info["ram_total"] = memory.total
        info["ram_available"] = memory.available
        info["ram_used"] = memory.used
        info["ram_percent"] = memory.percent
    except Exception:
        pass


def _collect_disks(psutil_module, info):
    try:
        partitions = psutil_module.disk_partitions(all=False)
    except Exception:
        return

    disk_info = []
    for partition in partitions:
        try:
            usage = psutil_module.disk_usage(partition.mountpoint)
        except Exception:
            continue
        disk_info.append(
            {
                "device": partition.device,
                "mountpoint": partition.mountpoint,
                "fstype": partition.fstype,
                "total": usage.total,
                "used": usage.used,
                "free": usage.free,
                "percent": usage.percent,
            }
        )
    info["disk_info"] = disk_info


def _collect_cpu(psutil_module, info):
    try:
        info["cpu_count_physical"] = psutil_module.cpu_count(logical=False)
        info["cpu_count_logical"] = psutil_module.cpu_count(logical=True)
    except Exception:
        pass


def format_gpu_result(gpu_result):
    """Format a getGpuInfo result exactly as the welcome screen expects."""
    if (
        not gpu_result
        or not isinstance(gpu_result, dict)
        or not gpu_result.get("success", False)
    ):
        return None
    gpus = gpu_result.get("gpus", [])
    if not gpus:
        return None
    return "\n".join(
        _format_gpu_line(index, gpu)
        for index, gpu in enumerate(gpus, start=1)
    )


def _format_gpu_line(index, gpu):
    name = gpu.get("name", "Unknown GPU")
    vendor = gpu.get("vendor", "")
    line = f"{index}. {name}"
    if vendor:
        line += f" [{vendor}]"
    line += _format_gpu_memory(gpu.get("memory", {}))
    if "temperature_celsius" in gpu:
        line += f" | Temp: {gpu['temperature_celsius']} °C"
    if "utilization_percent" in gpu:
        line += f" | Usage: {gpu['utilization_percent']}%"
    return line


def _format_gpu_memory(memory):
    if not memory:
        return ""
    if "total_mib" in memory:
        total = memory["total_mib"]
        used = memory.get("used_mib")
        if used is not None:
            return f" | Memory: {used}/{total} MiB"
        return f" | Memory: {total} MiB"
    if "total_readable" in memory:
        return f" | Memory: {memory['total_readable']}"
    if "reported" in memory:
        return f" | Memory: {memory['reported']}"
    return ""
