"""Process collection and presentation for listProcesses."""

from __future__ import annotations

import time


VALID_SORT_FIELDS = ("pid", "cpu", "memory", "name")
DEFAULT_LIMIT = 25
CPU_SAMPLE_SECONDS = 0.5
HUNDRED_NS_PER_SECOND = 10_000_000
# Attributes that are cheap to read for every process through psutil. On
# Windows, status() and num_threads() (and, for protected processes, most
# other fields) fall back to a complete system snapshot per call, so the
# Windows path reads one native snapshot instead (see
# _windows_process_snapshot) and psutil remains the portable fallback.
LISTING_ATTRIBUTES = (
    "pid", "name", "username", "memory_info", "memory_percent", "create_time", "exe",
)
# Windows reports "System Idle Process" (PID 0) with the idle CPU time; it is
# not a real process and would always top a CPU ranking.
WINDOWS_IDLE_PID = 0


def _limit_value(limit):
    if limit is None:
        return DEFAULT_LIMIT, None
    if limit == "null":
        return 0, None
    try:
        value = int(limit)
    except ValueError:
        value = -1
    if value >= 0:
        return value, None
    return None, {
        "success": False,
        "error": f"limit must be a non-negative integer, received '{limit}'",
        "message": (
            "Error: The 'limit' parameter must be a non-negative integer "
            f"(0 lists every process), but received '{limit}'"
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


def _process_errors(psutil_module):
    return (
        psutil_module.NoSuchProcess,
        psutil_module.AccessDenied,
        psutil_module.ZombieProcess,
    )


def _is_listed(row, filter_str, skip_idle):
    if row is None or (skip_idle and row["pid"] == WINDOWS_IDLE_PID):
        return False
    return not filter_str or filter_str.lower() in row["name"].lower()


# --- Windows: two native system snapshots -------------------------------------

def _cpu_from_snapshots(record, previous, elapsed):
    if previous is None or previous.get("create_time") != record.get("create_time"):
        return None
    delta = max(record["cpu_time_100ns"] - previous["cpu_time_100ns"], 0)
    return round(delta * 100.0 / (elapsed * HUNDRED_NS_PER_SECOND), 1)


def _snapshot_row(command, pid, record, cpu_percent, total_memory):
    rss = record["memory_rss"]
    return {
        "pid": pid,
        "name": record["name"],
        "cpu_percent": cpu_percent,
        "memory_percent": round(rss * 100.0 / total_memory, 3) if total_memory else 0.0,
        "username": None,
        "memory_rss": rss,
        "memory_rss_readable": command._format_bytes(rss),
        "create_time": record["create_time"],
        "status": record["status"],
        "num_threads": record["num_threads"],
    }


def _windows_entries(command, psutil_module, filter_str):
    first = command._process_snapshot()
    if first is None:
        return None
    started = time.perf_counter()
    command._wait_for_cpu_sample(CPU_SAMPLE_SECONDS)
    second = command._process_snapshot()
    if second is None:
        return None
    # The real wait is never shorter than the requested sample window.
    elapsed = max(time.perf_counter() - started, CPU_SAMPLE_SECONDS)
    total_memory = psutil_module.virtual_memory().total
    entries = []
    for pid, record in second.items():
        cpu = _cpu_from_snapshots(record, first.get(pid), elapsed)
        row = _snapshot_row(command, pid, record, cpu, total_memory)
        if _is_listed(row, filter_str, skip_idle=True):
            entries.append((pid, row))
    return entries


def _attach_identity(psutil_module, entries):
    """Owner and executable for displayed Windows rows (cheap token reads)."""
    errors = _process_errors(psutil_module)
    for pid, row in entries:
        try:
            process = psutil_module.Process(pid)
        except errors:
            continue
        for field, reader in (("username", process.username), ("exe", process.exe)):
            try:
                value = reader()
            except errors:
                continue
            if value:
                row[field] = value


# --- Portable psutil path ---------------------------------------------------

def _listing_row(command, info):
    if not info.get("name"):
        return None
    row = {
        "pid": info["pid"],
        "name": info["name"],
        "cpu_percent": None,
        "memory_percent": round(info.get("memory_percent") or 0.0, 3),
        "username": info.get("username"),
    }
    memory = info.get("memory_info")
    if memory is not None:
        row["memory_rss"] = memory.rss
        row["memory_rss_readable"] = command._format_bytes(memory.rss)
    if info.get("create_time") is not None:
        row["create_time"] = info["create_time"]
    if info.get("exe"):
        row["exe"] = info["exe"]
    return row


def _collect_processes(command, psutil_module, filter_str):
    """Return (process, row) pairs using only cheap per-process attributes."""
    entries = []
    skip_idle = command._platform_system() == "Windows"
    for proc in psutil_module.process_iter(list(LISTING_ATTRIBUTES)):
        try:
            row = _listing_row(command, proc.info)
        except _process_errors(psutil_module):
            continue
        if _is_listed(row, filter_str, skip_idle):
            entries.append((proc, row))
    return entries


def _sample_cpu(command, psutil_module, entries):
    """Measure real CPU usage over one short window.

    psutil's first cpu_percent() call per process always returns a meaningless
    0.0, so a single pass cannot rank processes by CPU.
    """
    errors = _process_errors(psutil_module)
    for proc, _row in entries:
        try:
            proc.cpu_percent(None)
        except errors:
            pass
    command._wait_for_cpu_sample(CPU_SAMPLE_SECONDS)
    for proc, row in entries:
        try:
            row["cpu_percent"] = round(proc.cpu_percent(None), 1)
        except errors:
            row["cpu_percent"] = None


def _attach_details(psutil_module, entries):
    """Read status and thread count only for the rows being returned."""
    errors = _process_errors(psutil_module)
    for proc, row in entries:
        try:
            with proc.oneshot():
                row["status"] = proc.status()
                row["num_threads"] = proc.num_threads()
        except errors:
            row.setdefault("status", None)


def _platform_entries(command, psutil_module, filter_str):
    if command._platform_system() == "Windows":
        entries = _windows_entries(command, psutil_module, filter_str)
        if entries is not None:
            return entries, _attach_identity, "windows_system_snapshot"
    entries = _collect_processes(command, psutil_module, filter_str)
    _sample_cpu(command, psutil_module, entries)
    return entries, _attach_details, "psutil"


# --- Presentation -----------------------------------------------------------

def _sort_entries(entries, sort_by):
    keys = {
        "pid": lambda entry: entry[1]["pid"],
        "cpu": lambda entry: entry[1]["cpu_percent"] or 0,
        "memory": lambda entry: entry[1]["memory_percent"] or 0,
        "name": lambda entry: entry[1]["name"].lower(),
    }
    entries.sort(key=keys[sort_by], reverse=sort_by in ("cpu", "memory"))


def _stats(processes):
    if not processes:
        return None
    top_cpu = max(processes, key=lambda row: row["cpu_percent"] or 0)
    top_memory = max(processes, key=lambda row: row["memory_percent"] or 0)
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


def _message(total, displayed, filter_str, sort_by, stats):
    filter_text = f" containing '{filter_str}'" if filter_str else ""
    message = (
        f"Found {total} processes{filter_text}, sorted by {sort_by}. "
        f"Displaying {displayed} result(s)"
    )
    message += (
        f" (pass limit 0 to list all {total}). " if displayed < total else ". "
    )
    if stats is None:
        return message
    cpu = stats["top_cpu_process"]
    memory = stats["top_memory_process"]
    return message + (
        f"Highest CPU process: {cpu['name']} "
        f"(PID {cpu['pid']}, {cpu['cpu_percent'] or 0:.1f}% of one CPU over "
        f"{CPU_SAMPLE_SECONDS:g} s). "
        f"Highest memory process: {memory['name']} "
        f"(PID {memory['pid']}, {memory['memory_percent']:.1f}% memory, "
        f"{memory['memory_rss_readable']})."
    )


def _missing_psutil():
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


def _inventory(command, psutil_module, filter_str, sort_by, limit):
    entries, finish, method = _platform_entries(command, psutil_module, filter_str)
    _sort_entries(entries, sort_by)
    total = len(entries)
    shown = entries[:limit] if limit > 0 else entries
    finish(psutil_module, shown)
    processes = [row for _handle, row in shown]
    stats = _stats(processes)
    result = {
        "filter": filter_str,
        "sort_by": sort_by,
        "limit": limit if limit > 0 else None,
        "os_type": command._platform_system().lower(),
        "processes": processes,
        "total_processes": total,
        "displayed_processes": len(processes),
        "collection_method": method,
        "cpu_sample_seconds": CPU_SAMPLE_SECONDS,
        "cpu_percent_scale": "percent of one logical CPU; can exceed 100 on multi-core systems",
        "success": True,
        "message": _message(total, len(processes), filter_str, sort_by, stats),
    }
    if stats is not None:
        result["stats"] = stats
    return result


def execute_processes(command, filter_str=None, sort_by="cpu", limit=None):
    """Run the public listProcesses workflow."""
    try:
        psutil_module = command._load_psutil()
    except ImportError:
        return _missing_psutil()
    try:
        request, error = _normalize_request(filter_str, sort_by, limit)
        if error:
            return error
        return _inventory(command, psutil_module, *request)
    except Exception as exc:
        return {
            "success": False,
            "error": f"Error listing processes: {str(exc)}",
            "message": f"Failed to list processes: {str(exc)}",
        }


def wait_for_cpu_sample(seconds):
    """Default sampling wait; tests replace it to stay deterministic."""
    time.sleep(seconds)
