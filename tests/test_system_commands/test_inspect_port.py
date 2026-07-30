#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Real socket and process tests for inspectPort."""

import socket
import subprocess
import sys

from qzx.commands.system.inspect_port import InspectPortCommand


class DarwinFallbackInspectPortCommand(InspectPortCommand):
    """Exercise the macOS lsof fallback with deterministic native evidence."""

    def __init__(self, listener_pid):
        super().__init__()
        self.listener_pid = listener_pid
        self.terminated = False

    @staticmethod
    def _system_name():
        return "Darwin"

    def _subprocess_text(self, command):
        if command[0] == "kill":
            self.terminated = True
            return subprocess.CompletedProcess(command, 0, "", "")
        if command[0] == "lsof" and "-sTCP:LISTEN" in command:
            stdout = "" if self.terminated else f"{self.listener_pid}\n"
            returncode = 1 if self.terminated else 0
            return subprocess.CompletedProcess(command, returncode, stdout, "")
        return subprocess.CompletedProcess(command, 1, "", "")


def test_invalid_port_type():
    result = InspectPortCommand().execute("not_a_port")
    assert result["success"] is False
    assert result["error_code"] == "invalid_port"
    assert "Port must be an integer" in result["error"]


def test_invalid_port_range():
    result = InspectPortCommand().execute(70000)

    assert result["success"] is False
    assert result["error_code"] == "invalid_port"
    assert "between 1 and 65535" in result["error"]


def test_invalid_kill_choice_is_not_silently_treated_as_false():
    result = InspectPortCommand().execute(12345, kill="sometimes")

    assert result["success"] is False
    assert result["error_code"] == "invalid_kill"
    assert result["error"]
    assert result["remediation"]
    assert "true or false" in result["message"]


def test_detects_a_real_listening_socket_without_killing_it():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]

        result = InspectPortCommand().execute(port)

    assert result["success"] is True, result
    assert result["port"] == port
    assert result["in_use"] is True
    assert result["killed"] is False


def test_legacy_kill_option_never_terminates_a_controlled_real_child():
    child_code = (
        "import socket,sys,time;"
        "s=socket.socket();"
        "s.bind(('127.0.0.1',0));"
        "s.listen(1);"
        "print(s.getsockname()[1],flush=True);"
        "time.sleep(30)"
    )
    child = subprocess.Popen(
        [sys.executable, "-c", child_code],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        port = int(child.stdout.readline().strip())
        inspection = InspectPortCommand().execute(port)
        assert inspection["success"] is True, inspection
        assert inspection["in_use"] is True

        result = InspectPortCommand().execute(port, kill=True)

        assert result["success"] is False
        assert result["error_code"] == "operation_moved"
        assert result["status"] == "read_only"
        assert result["in_use"] is True
        assert result["killed"] is False
        assert child.poll() is None

        if result["observed_pids"]:
            assert child.pid in result["observed_pids"]
            suggestions = result["details"]["suggested_commands"]
            assert any(f"killProcess {child.pid}" in item for item in suggestions)
            assert any("--expected-create-time" in item for item in suggestions)
    finally:
        if child.poll() is None:
            child.terminate()
            child.wait(timeout=5)


def test_macos_fallback_legacy_kill_returns_guidance_without_termination():
    command = DarwinFallbackInspectPortCommand(listener_pid=424242)

    result = command._execute_fallback(
        54321,
        kill_process=True,
        expected_pid=424242,
    )

    assert result["success"] is False
    assert result["error_code"] == "operation_moved"
    assert result["status"] == "read_only"
    assert result["killed"] is False
    assert result["observed_pids"] == [424242]
    assert command.terminated is False
    assert result["details"]["suggested_commands"] == [
        "qzx killProcess 424242 --yolo"
    ]


def test_inspect_port_metadata_is_read_only():
    command = InspectPortCommand()

    assert command.requires_explicit_approval is False
    assert command.approval_when_parameter is None
