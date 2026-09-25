"""Native-tool fallbacks for inspectPort."""

from __future__ import annotations

import locale
import subprocess

from qzx.commands.system._inspect_port_results import (
    failed_result,
    free_port_result,
    occupied_result,
    unavailable_result,
    unknown_process,
)


def subprocess_text(command):
    """Run one bounded native diagnostic using the host text encoding."""
    return subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding=locale.getencoding(),
        errors="replace",
        timeout=20,
        check=False,
    )


def endpoint_port(endpoint):
    """Extract an exact numeric port from netstat IPv4/IPv6 endpoints."""
    if not endpoint or ":" not in endpoint:
        return None
    try:
        return int(endpoint.rsplit(":", 1)[-1])
    except ValueError:
        return None


def lsof_listener_pids(port_num, runner):
    """Return listener PIDs and whether both TCP and UDP probes succeeded."""
    pids = set()
    errors = []
    commands = (
        ["lsof", "-nP", "-t", f"-iTCP:{port_num}", "-sTCP:LISTEN"],
        ["lsof", "-nP", "-t", f"-iUDP:{port_num}"],
    )
    for command in commands:
        result = runner(command)
        if result.returncode not in (0, 1):
            errors.append(_diagnostic_text(command[0], result))
            continue
        if result.returncode == 0:
            pids.update(_integer_lines(result.stdout))
    return pids, not errors, errors


def native_process_name(pid, is_windows, runner):
    """Resolve a process name without mutating process state."""
    if is_windows:
        return _windows_process_name(pid, runner)
    result = runner(["ps", "-p", str(pid), "-o", "comm="])
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip().splitlines()[0]
    return "unknown"


def execute_fallback(port_num, system_name, runner, process_name_reader):
    """Inspect with native tools when psutil is unavailable or restricted."""
    try:
        if system_name == "windows":
            pids, failure = _windows_listener_pids(port_num, runner)
            if failure:
                return failure
        elif system_name == "sunos":
            return _inspect_sunos(port_num, runner)
        else:
            pids, available, errors = lsof_listener_pids(port_num, runner)
            if not available:
                return unavailable_result(port_num, "lsof", "; ".join(errors))
        if not pids:
            return free_port_result(port_num)
        return _native_occupied_result(port_num, pids, process_name_reader)
    except (OSError, subprocess.SubprocessError) as exc:
        return failed_result(port_num, exc)


def fallback_failure(port_num, tool_name, result):
    """Convert a failed native tool invocation to the public result contract."""
    return unavailable_result(port_num, tool_name, _diagnostic_text(tool_name, result))


def _windows_listener_pids(port_num, runner):
    result = runner(["netstat", "-ano"])
    if result.returncode != 0:
        return set(), fallback_failure(port_num, "netstat", result)
    pids = set()
    for line in result.stdout.splitlines():
        parts = line.strip().split()
        if _windows_listener_pid(parts, port_num) is not None:
            pids.add(_windows_listener_pid(parts, port_num))
    return pids, None


def _windows_listener_pid(parts, port_num):
    if len(parts) < 4 or endpoint_port(parts[1]) != port_num:
        return None
    protocol = parts[0].upper()
    if protocol == "TCP" and (len(parts) < 5 or parts[-2].upper() != "LISTENING"):
        return None
    if protocol not in {"TCP", "UDP"}:
        return None
    try:
        return int(parts[-1])
    except ValueError:
        return None


def _inspect_sunos(port_num, runner):
    result = runner(["netstat", "-an", "-P", "tcp"])
    if result.returncode != 0:
        return fallback_failure(port_num, "SunOS netstat", result)
    if not _sunos_has_listener(result.stdout, port_num):
        return free_port_result(port_num)
    limitation = (
        "SunOS netstat confirms the listening port but does not expose its "
        "owning PID in this mode."
    )
    return occupied_result(port_num, [], [], [limitation])


def _sunos_has_listener(output, port_num):
    suffixes = (f".{port_num}", f":{port_num}")
    for line in output.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        if parts[-1].upper() not in {"LISTEN", "LISTENING"}:
            continue
        if parts[0].endswith(suffixes):
            return True
    return False


def _native_occupied_result(port_num, pids, process_name_reader):
    processes = []
    for pid in sorted(pids):
        process = unknown_process(pid, status="active")
        process["name"] = process_name_reader(pid)
        processes.append(process)
    limitation = (
        "Native fallback inspection could not obtain process creation timestamps; "
        "re-inspect with psutil before terminating a PID."
    )
    return occupied_result(port_num, sorted(pids), processes, [limitation])


def _windows_process_name(pid, runner):
    result = runner(["tasklist", "/NH", "/FI", f"PID eq {pid}"])
    if result.returncode != 0 or "No tasks" in result.stdout:
        return "unknown"
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("="):
            return stripped.split()[0]
    return "unknown"


def _integer_lines(output):
    values = set()
    for line in output.splitlines():
        try:
            values.add(int(line.strip()))
        except ValueError:
            continue
    return values


def _diagnostic_text(tool_name, result):
    return (
        result.stderr.strip()
        or result.stdout.strip()
        or f"{tool_name} exited with code {result.returncode}"
    )
