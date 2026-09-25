"""Result helpers for the read-only inspectPort command."""

from __future__ import annotations


def parse_port(port):
    """Return a normalized port number or the public validation error."""
    try:
        port_num = int(port)
    except (TypeError, ValueError):
        return {
            "success": False,
            "error_code": "invalid_port",
            "error": f"Port must be an integer, received {port!r}.",
            "message": f"Failed to inspect port: expected an integer, got {port!r}.",
        }
    if not 1 <= port_num <= 65535:
        return {
            "success": False,
            "error_code": "invalid_port",
            "error": f"Port must be between 1 and 65535, received {port_num}.",
            "message": (
                "Failed to inspect port: port numbers range from 1 to "
                f"65535, but {port_num} was requested."
            ),
        }
    return port_num


def unknown_process(pid, *, status="unknown"):
    """Build the stable placeholder used when process details are unavailable."""
    return {
        "pid": pid,
        "name": "unknown",
        "status": status,
        "create_time": None,
        "executable": None,
        "command": [],
        "username": None,
        "memory": None,
    }


def occupied_result(port_num, pids, processes, limitations, *, errors=None):
    """Build the stable successful result for an occupied port."""
    observed_pids = sorted(pids)
    names = [process["name"] for process in processes if process.get("name")]
    owner_summary = ", ".join(names) if names else "an owner not exposed by the OS"
    pid_summary = ", ".join(str(pid) for pid in observed_pids) or "unavailable"
    return {
        "success": True,
        "status": "in_use",
        "port": port_num,
        "in_use": True,
        "observed_pids": observed_pids,
        "processes": processes,
        "limitations": limitations,
        "errors": errors or [],
        "message": (
            f"Port {port_num} is in use by {owner_summary} "
            f"(PID(s): {pid_summary}). No process state was changed."
        ),
    }


def free_port_result(port_num):
    """Build the stable successful result for a free port."""
    return {
        "success": True,
        "status": "free",
        "port": port_num,
        "in_use": False,
        "observed_pids": [],
        "processes": [],
        "message": f"Port {port_num} is free.",
    }


def unavailable_result(port_num, tool_name, diagnostic):
    """Report that the selected native inspection tool could not run."""
    return {
        "success": False,
        "error_code": "inspection_unavailable",
        "error": diagnostic,
        "port": port_num,
        "in_use": None,
        "message": f"Could not inspect port {port_num} with {tool_name}: {diagnostic}",
    }


def failed_result(port_num, exc):
    """Report an unexpected native-inspection failure without mutating state."""
    error = f"{type(exc).__name__}: {exc}"
    return {
        "success": False,
        "error_code": "inspection_failed",
        "error": error,
        "port": port_num,
        "in_use": None,
        "message": f"Native inspection failed for port {port_num}: {error}",
    }
