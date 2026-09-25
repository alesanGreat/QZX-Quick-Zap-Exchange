"""Process collection and presentation for listProcesses."""

from __future__ import annotations

import platform


VALID_SORT_FIELDS = ("pid", "cpu", "memory", "name")


def _limit_value(limit):
    if limit == "null":
        return 0, None
    if limit is None:
        return None, None
    try:
        return int(limit), None
    except ValueError:
        return None, {
            "success": False,
            "error": f"limit must be an integer, received '{limit}'",
            "message": (
                f"Error: The 'limit' parameter must be an integer, "
                f"but received '{limit}'"
            ),
        }


def _normalize_request(filter_str, sort_by, limit):
    limit, error = _limit_value(limit)
    if error:
        return None, error
    if filter_str == "null":
        filter_str = None
    if sort_by not in VALID_SORT_FIELDS:
        return None, {
            "success": False,
            "error": (
                f"sort_by must be one of {list(VALID_SORT_FIELDS)}, "
                f"received '{sort_by}'"
            ),
            "message": (
                "Error: The 'sort_by' parameter must be one of these values: "
                f"{', '.join(VALID_SORT_FIELDS)}, but received '{sort_by}'"
            ),
        }
    return (filter_str, sort_by, limit), None


def _process_row(command, proc, psutil_module):
    info = proc.info
    if not info["name"]:
        return None
    row = {
        "pid": info["pid"],
        "name": info["name"],
        "cpu_percent": info["cpu_percent"] or 0.0,
        "memory_percent": info["memory_percent"] or 0.0,
        "username": info["username"],
        "status": info["status"],
    }
    try:
        row["num_threads"] = proc.num_threads()
        row["create_time"] = proc.create_time()
        memory = proc.memory_info()
        row["memory_rss"] = memory.rss
        row["memory_rss_readable"] = command._format_bytes(memory.rss)
        try:
            row["exe"] = proc.exe()
        except (psutil_module.AccessDenied, psutil_module.ZombieProcess):
            pass
    except (psutil_module.AccessDenied, psutil_module.ZombieProcess):
        pass
    return row


def _collect_processes(command, psutil_module, filter_str):
    processes = []
    attrs = ["pid", "name", "cpu_percent", "memory_percent", "username", "status"]
    for proc in psutil_module.process_iter(attrs):
        try:
            row = _process_row(command, proc, psutil_module)
            if row is None:
                continue
            if filter_str and filter_str.lower() not in row["name"].lower():
                continue
            processes.append(row)
        except (
            psutil_module.NoSuchProcess,
            psutil_module.AccessDenied,
            psutil_module.ZombieProcess,
        ):
            pass
    return processes


def _sort_processes(processes, sort_by):
    keys = {
        "pid": lambda row: row["pid"],
        "cpu": lambda row: row["cpu_percent"] or 0,
        "memory": lambda row: row["memory_percent"] or 0,
        "name": lambda row: row["name"].lower() if row["name"] else "",
    }
    processes.sort(
        key=keys[sort_by],
        reverse=sort_by in ("cpu", "memory"),
    )


def _stats(processes):
    if not processes:
        return None
    top_cpu = max(processes, key=lambda row: row["cpu_percent"])
    top_memory = max(processes, key=lambda row: row["memory_percent"])
    return {
        "top_cpu_process": {
            "pid": top_cpu["pid"],
            "name": top_cpu["name"],
            "cpu_percent": top_cpu["cpu_percent"],
        },
        "top_memory_process": {
            "pid": top_memory["pid"],
            "name": top_memory["name"],
            "memory_percent": top_memory["memory_percent"],
            "memory_rss_readable": top_memory.get("memory_rss_readable", "N/A"),
        },
    }


def _message(total, displayed, filter_str, sort_by, limit, stats):
    filter_text = f" containing '{filter_str}'" if filter_str else ""
    limit_text = f", showing top {limit}" if limit > 0 else ""
    message = (
        f"Found {total} processes{filter_text}, sorted by {sort_by}{limit_text}. "
        f"Displaying {displayed} result(s). "
    )
    if stats is None:
        return message
    cpu = stats["top_cpu_process"]
    memory = stats["top_memory_process"]
    return message + (
        f"Highest CPU process: {cpu['name']} "
        f"(PID {cpu['pid']}, {cpu['cpu_percent']:.1f}% CPU). "
        f"Highest memory process: {memory['name']} "
        f"(PID {memory['pid']}, {memory['memory_percent']:.1f}% memory, "
        f"{memory['memory_rss_readable']})."
    )


def execute_processes(command, filter_str=None, sort_by="cpu", limit=0):
    """Run the public listProcesses workflow."""
    try:
        psutil_module = command._load_psutil()
    except ImportError:
        return {
            "success": False,
            "error": (
                "The psutil module is required for this command. "
                "Install it with: pip install psutil"
            ),
            "message": (
                "Failed to list processes: psutil module is not installed. "
                "Please install it with: pip install psutil"
            ),
        }
    try:
        request, error = _normalize_request(filter_str, sort_by, limit)
        if error:
            return error
        filter_str, sort_by, limit = request
        processes = _collect_processes(command, psutil_module, filter_str)
        _sort_processes(processes, sort_by)
        total = len(processes)
        if limit > 0:
            processes = processes[:limit]
        stats = _stats(processes)
        result = {
            "filter": filter_str,
            "sort_by": sort_by,
            "limit": limit if limit > 0 else None,
            "os_type": platform.system().lower(),
            "processes": processes,
            "total_processes": total,
            "displayed_processes": len(processes),
            "success": True,
            "message": _message(
                total, len(processes), filter_str, sort_by, limit, stats
            ),
        }
        if stats is not None:
            result["stats"] = stats
        return result
    except Exception as exc:
        return {
            "success": False,
            "error": f"Error listing processes: {str(exc)}",
            "message": f"Failed to list processes: {str(exc)}",
        }
