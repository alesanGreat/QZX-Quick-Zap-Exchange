#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Real socket and process tests for inspectPort."""

import platform
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


def test_kill_operates_only_on_a_controlled_real_child_process():
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

        if platform.system().lower() == "sunos":
            result = InspectPortCommand().execute(port, kill=True)
            assert result["success"] is False
            assert result["in_use"] is True
            assert result["killed"] is False
            assert child.poll() is None
        else:
            assert inspection["success"] is True, inspection
            observed_pids = {
                process["pid"]
                for process in inspection["processes"]
            }
            assert observed_pids

            unconfirmed = InspectPortCommand().execute(port, kill=True)
            assert unconfirmed["success"] is False
            assert unconfirmed["error_code"] == "expected_pid_required"
            assert unconfirmed["killed"] is False
            assert child.poll() is None

            observed_pid = next(iter(observed_pids))
            result = InspectPortCommand().execute(
                port,
                kill=True,
                expected_pid=observed_pid,
            )
            assert result["success"] is True, result
            assert result["in_use"] is True
            assert result["killed"] is True
            assert result["killed_pids"] == [observed_pid]
            assert result["port_cleared"] is True
            assert result["remaining_pids"] == []
            child.wait(timeout=5)
    finally:
        if child.poll() is None:
            child.terminate()
            child.wait(timeout=5)


def test_macos_fallback_verifies_port_after_controlled_termination():
    command = DarwinFallbackInspectPortCommand(listener_pid=424242)

    result = command._execute_fallback(
        54321,
        kill_process=True,
        expected_pid=424242,
    )

    assert result["success"] is True
    assert result["killed"] is True
    assert result["killed_pids"] == [424242]
    assert result["port_cleared"] is True
    assert result["remaining_pids"] == []
    assert "verified that port 54321 is clear" in result["message"]
