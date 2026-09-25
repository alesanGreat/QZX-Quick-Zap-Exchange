"""RAM and swap result assembly for getRamInfo."""

from __future__ import annotations


OPTIONAL_MEMORY_FIELDS = ("active", "inactive", "buffers", "cached", "shared", "slab")


def _memory_row(command, memory):
    return {
        "total": memory.total,
        "total_readable": command._format_bytes(memory.total),
        "available": memory.available,
        "available_readable": command._format_bytes(memory.available),
        "used": memory.used,
        "used_readable": command._format_bytes(memory.used),
        "free": memory.free,
        "free_readable": command._format_bytes(memory.free),
        "percent": memory.percent,
    }


def _swap_row(command, swap):
    row = {
        "total": swap.total,
        "total_readable": command._format_bytes(swap.total),
        "used": swap.used,
        "used_readable": command._format_bytes(swap.used),
        "free": swap.free,
        "free_readable": command._format_bytes(swap.free),
        "percent": swap.percent,
    }
    try:
        if hasattr(swap, "sin") and hasattr(swap, "sout"):
            row["sin"] = swap.sin
            row["sout"] = swap.sout
    except Exception:
        pass
    return row


def _optional_memory_stats(command, memory):
    stats = {}
    try:
        for name in OPTIONAL_MEMORY_FIELDS:
            if not hasattr(memory, name):
                continue
            value = getattr(memory, name)
            stats[name] = {
                "value": value,
                "readable": command._format_bytes(value),
            }
    except Exception:
        pass
    return stats


def _message(ram_info):
    memory = ram_info["virtual_memory"]
    swap = ram_info["swap"]
    message = (
        f"RAM usage: {memory['used_readable']} of {memory['total_readable']} "
        f"({round(memory['percent'], 1)}%) used, "
        f"{memory['available_readable']} available. "
    )
    if swap["total"] > 0:
        message += (
            f"Swap: {swap['used_readable']} of {swap['total_readable']} "
            f"({round(swap['percent'], 1)}%) used, "
            f"{swap['free_readable']} free."
        )
    else:
        message += "No swap space configured."
    stats = ram_info.get("memory_stats", {})
    if "cached" in stats:
        message += f" Cached memory: {stats['cached']['readable']}."
    if "buffers" in stats:
        message += f" Buffers: {stats['buffers']['readable']}."
    return message


def execute_ram_info(command):
    """Run the public getRamInfo workflow."""
    try:
        memory = command._virtual_memory()
        swap = command._swap_memory()
        ram_info = {
            "virtual_memory": _memory_row(command, memory),
            "swap": _swap_row(command, swap),
        }
        stats = _optional_memory_stats(command, memory)
        if stats:
            ram_info["memory_stats"] = stats
        return {
            "success": True,
            "message": _message(ram_info),
            "ram_info": ram_info,
        }
    except Exception as exc:
        return {
            "success": False,
            "error": f"Error getting RAM information: {str(exc)}",
            "message": (
                f"Failed to retrieve system memory information: {str(exc)}"
            ),
        }
