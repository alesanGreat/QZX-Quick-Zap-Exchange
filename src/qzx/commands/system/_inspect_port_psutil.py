"""psutil-specific helpers for inspectPort."""

from __future__ import annotations

import socket

from qzx.commands.system._inspect_port_results import unknown_process


def is_bound_socket(connection, psutil_module):
    """Accept TCP listeners and bound UDP sockets, not client connections."""
    if connection.type == socket.SOCK_DGRAM:
        return True
    return connection.status in {
        psutil_module.CONN_LISTEN,
        "LISTEN",
        "LISTENING",
    }


def matching_connections(connections, port_num, psutil_module):
    """Return bound local sockets that exactly match the requested port."""
    return [
        connection
        for connection in connections
        if connection.laddr
        and connection.laddr.port == port_num
        and is_bound_socket(connection, psutil_module)
    ]


def owner_pids(connections):
    """Return stable unique owning PIDs exposed by the operating system."""
    return sorted(
        {connection.pid for connection in connections if connection.pid is not None}
    )


def inspect_process(pid, psutil_module, format_bytes):
    """Read one process defensively without treating optional details as required."""
    try:
        process = psutil_module.Process(pid)
        info = _basic_process_info(process, pid)
    except psutil_module.NoSuchProcess:
        return _process_error(pid, "exited while QZX was collecting its details")
    except psutil_module.AccessDenied:
        return _process_error(pid, "was denied by the operating system")
    except Exception as exc:
        return {
            "success": False,
            "error": f"Could not inspect PID {pid}: {type(exc).__name__}: {exc}",
        }
    _add_optional_details(info, process, psutil_module, format_bytes)
    return {"success": True, "process": info}


def _basic_process_info(process, pid):
    return {
        "pid": pid,
        "name": process.name(),
        "status": process.status(),
        "create_time": process.create_time(),
        "executable": None,
        "command": [],
        "username": None,
        "memory": None,
    }


def _add_optional_details(info, process, psutil_module, format_bytes):
    try:
        info["executable"] = process.exe()
        info["command"] = process.cmdline()
        info["username"] = process.username()
        memory = process.memory_info()
        info["memory"] = {
            "rss_bytes": memory.rss,
            "rss_formatted": format_bytes(memory.rss),
        }
    except (
        psutil_module.AccessDenied,
        psutil_module.NoSuchProcess,
        psutil_module.ZombieProcess,
    ):
        pass


def _process_error(pid, reason):
    if reason.startswith("exited"):
        message = f"PID {pid} {reason}."
    else:
        message = f"Access to details for PID {pid} {reason}."
    return {"success": False, "error": message}


def inspect_processes(pids, psutil_module, format_bytes):
    """Collect process evidence while preserving partial failures."""
    processes = []
    errors = []
    for pid in pids:
        inspected = inspect_process(pid, psutil_module, format_bytes)
        if inspected["success"]:
            processes.append(inspected["process"])
            continue
        errors.append(inspected["error"])
        processes.append(unknown_process(pid))
    return processes, errors
