#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Integration checks that deliberately use real system APIs without mocks."""

import json
import os
from pathlib import Path
import socket
import subprocess
import sys

import psutil


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _run_qzx(*arguments):
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(REPOSITORY_ROOT / "src")
    environment["QZX_TELEMETRY"] = "0"
    return subprocess.run(
        [sys.executable, "-m", "qzx", *arguments, "--json"],
        cwd=REPOSITORY_ROOT,
        env=environment,
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )


def _require_json_success(completed):
    assert completed.returncode == 0, (
        f"QZX exited with {completed.returncode}.\n"
        f"stdout:\n{completed.stdout}\n"
        f"stderr:\n{completed.stderr}"
    )
    result = json.loads(completed.stdout)
    assert result["success"] is True, result
    return result


def test_real_psutil_core_apis():
    """Exercise the installed psutil extension against the real host kernel."""
    assert psutil.cpu_count(logical=True)
    assert psutil.virtual_memory().total > 0
    assert psutil.disk_usage(os.path.abspath(os.sep)).total > 0
    assert psutil.Process().pid == os.getpid()


def test_public_system_doctor_with_real_dependencies():
    """Run the public command without replacing psutil or platform APIs."""
    result = _require_json_success(
        _run_qzx("systemDoctor", "--quick", "false")
    )

    details = result["details"]
    assert details["cpu"]["cores_logical"] >= 1
    assert details["ram"]["virtual"]["total_bytes"] > 0
    assert isinstance(details["ports"]["listening"], list)


def test_public_inspect_port_against_real_listening_socket():
    """Detect a real controlled socket through the public QZX command."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]

        result = _require_json_success(_run_qzx("inspectPort", str(port)))

    assert result["port"] == port
    assert result["in_use"] is True
    assert result["status"] == "in_use"
    assert "killed" not in result
