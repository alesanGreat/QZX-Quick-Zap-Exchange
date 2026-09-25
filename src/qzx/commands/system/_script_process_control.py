"""Process-tree termination helpers for runScript."""

from __future__ import annotations

import os
import shutil
import signal
import subprocess


def terminate_process_tree(process, observe_tree, confirm_stopped):
    """Stop a timed-out script and verify the observed process tree."""
    method = "process_kill_fallback"
    process_tree_confirmed = False
    observed_processes = observe_tree(process.pid)

    if os.name == "nt":
        method, process_tree_confirmed = _terminate_windows_tree(process)
    else:
        method, process_tree_confirmed = _terminate_posix_group(process)

    _kill_root_if_needed(process)
    if observed_processes:
        process_tree_confirmed = confirm_stopped(observed_processes)

    return {
        "attempted": True,
        "scope": "process_tree",
        "method": method,
        "process_tree_confirmed": process_tree_confirmed,
        "root_process_stopped": process.poll() is not None,
    }


def _terminate_windows_tree(process):
    taskkill = shutil.which("taskkill.exe") or shutil.which("taskkill")
    if not taskkill:
        return "process_kill_fallback", False
    try:
        completed = subprocess.run(
            [taskkill, "/PID", str(process.pid), "/T", "/F"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return "taskkill_tree", completed.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return "process_kill_fallback", False


def _terminate_posix_group(process):
    try:
        os.killpg(process.pid, signal.SIGKILL)
        return "process_group_kill", True
    except OSError:
        return "process_kill_fallback", False


def _kill_root_if_needed(process):
    if process.poll() is None:
        try:
            process.kill()
        except OSError:
            pass
    try:
        process.wait(timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        pass
