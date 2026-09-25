"""GPU inventory orchestration for getGpuInfo."""

from __future__ import annotations


def invalid_detailed(value):
    return {
        "success": False,
        "error_code": "invalid_detailed",
        "error": f"detailed must be true or false; got {value!r}.",
        "message": (
            "Could not inspect GPUs because --detailed must be true or false."
        ),
        "details": {"received": value},
    }


def platform_gpus(command, warnings):
    system = command._system_name.casefold()
    if system == "windows":
        return command._windows_gpus(warnings), "Win32_VideoController"
    if system == "linux":
        return command._linux_gpus(warnings), "lspci"
    if system == "darwin":
        return command._macos_gpus(warnings), "system_profiler"
    warnings.append(
        {
            "code": "unsupported_platform_inventory",
            "message": (
                f"No generic GPU inventory provider is defined for "
                f"{command._system_name}."
            ),
        }
    )
    return [], None


def merge_gpus(preferred, additional):
    merged = list(preferred)
    keys = {
        (gpu.get("vendor", "").casefold(), gpu.get("name", "").casefold())
        for gpu in merged
    }
    preferred_vendors = {
        gpu.get("vendor", "").casefold() for gpu in preferred
    }
    for gpu in additional:
        key = (gpu.get("vendor", "").casefold(), gpu.get("name", "").casefold())
        if key in keys:
            continue
        if key[0] == "nvidia" and "nvidia" in preferred_vendors:
            continue
        row = dict(gpu)
        row["index"] = len(merged)
        merged.append(row)
        keys.add(key)
    return merged


def _message(command, gpus, vendors):
    if gpus:
        summary = ", ".join(vendors)
        plural = "" if len(gpus) == 1 else "s"
        return f"Detected {len(gpus)} GPU{plural} from {summary}."
    return (
        f"No GPU was detected on {command._system_name}. "
        "The required platform inventory utility may be unavailable."
    )


def execute_gpu_info(command, detailed=False):
    """Run the public getGpuInfo workflow."""
    detailed_value = command._parse_bool(detailed)
    if detailed_value is None:
        return invalid_detailed(detailed)
    warnings, sources = [], []
    gpus = command._nvidia_gpus(detailed_value, warnings)
    if gpus:
        sources.append("nvidia-smi")
    platform_rows, platform_source = command._platform_gpus(warnings)
    if platform_source:
        sources.append(platform_source)
    gpus = command._merge_gpus(gpus, platform_rows)
    vendors = sorted({gpu["vendor"] for gpu in gpus}, key=str.casefold)
    result = {
        "success": True,
        "message": _message(command, gpus, vendors),
        "gpu_count": len(gpus),
        "detected_vendors": vendors,
        "gpus": gpus,
        "details": {
            "platform": command._system_name,
            "detailed": detailed_value,
            "sources": sources,
        },
    }
    if warnings:
        result["warnings"] = warnings
    return result
