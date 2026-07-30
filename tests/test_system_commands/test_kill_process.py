"""Real controlled-process tests for killProcess."""

import os
import subprocess
import sys

from qzx.commands.system.kill_process import KillProcessCommand


def _sleeping_child():
    return subprocess.Popen([
        sys.executable,
        "-c",
        "import time; time.sleep(30)",
    ])


def test_invalid_arguments_fail_closed():
    command = KillProcessCommand()

    assert command.execute("pid")["error_code"] == "invalid_pid"
    assert command.execute(123, force="perhaps")["error_code"] == "invalid_force"
    assert command.execute(123, wait_seconds=0)["error_code"] == "invalid_wait_seconds"
    assert (
        command.execute(123, expected_create_time="yesterday")["error_code"]
        == "invalid_expected_create_time"
    )


def test_refuses_to_terminate_qzx_itself():
    result = KillProcessCommand().execute(os.getpid())

    assert result["success"] is False
    assert result["error_code"] == "protected_process"


def test_public_invocation_requires_explicit_bypass():
    child = _sleeping_child()
    try:
        result = KillProcessCommand().invoke([str(child.pid)])

        assert result["success"] is False
        assert result["error_code"] == "approval_required"
        assert child.poll() is None
    finally:
        if child.poll() is None:
            child.terminate()
            child.wait(timeout=5)


def test_expected_creation_time_blocks_pid_identity_mismatch():
    child = _sleeping_child()
    try:
        result = KillProcessCommand().execute(
            child.pid,
            expected_create_time=1.0,
        )

        assert result["success"] is False
        assert result["error_code"] == "process_identity_changed"
        assert child.poll() is None
    finally:
        if child.poll() is None:
            child.terminate()
            child.wait(timeout=5)


def test_public_bypass_terminates_controlled_child_and_verifies_exit():
    import psutil

    child = _sleeping_child()
    try:
        create_time = psutil.Process(child.pid).create_time()
        result = KillProcessCommand().invoke([
            str(child.pid),
            "--expected-create-time",
            str(create_time),
            "--yolo",
        ])

        assert result["success"] is True, result
        assert result["status"] == "terminated"
        assert result["process"]["pid"] == child.pid
        assert result["termination"]["verified_exited"] is True
        assert result["meta"]["safety_backup"]["status"] == "bypassed"
        child.wait(timeout=5)
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=5)
