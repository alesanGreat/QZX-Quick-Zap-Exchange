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


def test_detects_a_real_listening_socket_without_changing_it():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]

        result = InspectPortCommand().execute(port)

    assert result["success"] is True, result
    assert result["port"] == port
    assert result["in_use"] is True


def test_public_contract_only_accepts_the_port_parameter():
    command = InspectPortCommand()

    assert [parameter["name"] for parameter in command.parameters] == ["port"]


def test_inspecting_a_controlled_real_child_never_terminates_it():
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
        assert child.poll() is None
    finally:
        if child.poll() is None:
            child.terminate()
            child.wait(timeout=5)


def test_macos_fallback_is_read_only():
    command = DarwinFallbackInspectPortCommand(listener_pid=424242)

    result = command._execute_fallback(54321)

    assert result["success"] is True
    assert result["status"] == "in_use"
    assert result["observed_pids"] == [424242]
    assert command.terminated is False


def test_macos_uses_lsof_when_psutil_omits_a_visible_listener(monkeypatch):
    class IncompletePsutil:
        CONN_LISTEN = "LISTEN"

        @staticmethod
        def net_connections(kind):
            assert kind == "inet"
            return []

    monkeypatch.setitem(sys.modules, "psutil", IncompletePsutil)
    command = DarwinFallbackInspectPortCommand(listener_pid=424242)

    result = command.execute(54321)

    assert result["success"] is True
    assert result["in_use"] is True
    assert result["observed_pids"] == [424242]


def test_inspect_port_metadata_is_read_only():
    command = InspectPortCommand()

    assert command.requires_explicit_approval is False
    assert command.approval_when_parameter is None
