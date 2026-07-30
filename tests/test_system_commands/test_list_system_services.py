#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Real-platform tests for system-service discovery."""

import subprocess

from qzx.commands.system.list_system_services import ListSystemServicesCommand


def test_execute_lists_services_from_the_real_service_manager():
    result = ListSystemServicesCommand().execute()

    assert result["success"] is True, result
    assert result["service_manager"]
    assert result["status_filter"] == "all"
    assert result["total_services"] > 0
    assert result["total_services"] == len(result["services"])
    assert isinstance(result["errors"], list)
    for service in result["services"]:
        assert service["name"]
        assert service["status"] in {"running", "stopped"}


def test_running_filter_is_applied_to_real_services():
    result = ListSystemServicesCommand().execute(status="running")

    assert result["success"] is True, result
    assert result["status_filter"] == "running"
    assert all(service["status"] == "running" for service in result["services"])


def test_windows_collector_falls_back_to_sc_after_powershell_timeout():
    calls = []

    def find_executable(name):
        return {
            "powershell": "powershell.exe",
            "sc.exe": "sc.exe",
        }.get(name)

    def run_command(command, timeout=10):
        calls.append(command)
        if command[0] == "powershell.exe":
            raise subprocess.TimeoutExpired(command, timeout)
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=(
                "SERVICE_NAME: QZXFixture\n"
                "        STATE              : 4  RUNNING\n"
            ),
            stderr="",
        )

    command = ListSystemServicesCommand(
        executable_finder=find_executable,
        command_runner=run_command,
    )

    services, manager, errors = command._collect_windows_services()

    assert services == [
        {
            "name": "QZXFixture",
            "display_name": "QZXFixture",
            "status": "running",
        }
    ]
    assert manager == "Windows Service Control Manager (sc.exe)"
    assert errors == ["PowerShell Get-Service timed out after 10 seconds."]
    assert [call[0] for call in calls] == ["powershell.exe", "sc.exe"]


def test_windows_collector_falls_back_to_sc_after_malformed_powershell_json():
    calls = []

    def find_executable(name):
        return {
            "powershell": "powershell.exe",
            "sc.exe": "sc.exe",
        }.get(name)

    def run_command(command):
        calls.append(command)
        if command[0] == "powershell.exe":
            return subprocess.CompletedProcess(
                command,
                0,
                stdout='[{"Name":"truncated"',
                stderr="",
            )
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=(
                "SERVICE_NAME: QZXFixture\n"
                "        STATE              : 4  RUNNING\n"
            ),
            stderr="",
        )

    command = ListSystemServicesCommand(
        executable_finder=find_executable,
        command_runner=run_command,
    )

    services, manager, errors = command._collect_windows_services()

    assert services[0]["name"] == "QZXFixture"
    assert manager == "Windows Service Control Manager (sc.exe)"
    assert errors[0].startswith(
        "PowerShell Get-Service returned invalid JSON:"
    )
    assert [call[0] for call in calls] == ["powershell.exe", "sc.exe"]


def test_windows_collector_falls_back_after_unexpected_powershell_json_shape():
    def find_executable(name):
        return {
            "powershell": "powershell.exe",
            "sc.exe": "sc.exe",
        }.get(name)

    def run_command(command):
        if command[0] == "powershell.exe":
            return subprocess.CompletedProcess(
                command,
                0,
                stdout='"not a service record"',
                stderr="",
            )
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=(
                "SERVICE_NAME: QZXFixture\n"
                "        STATE              : 1  STOPPED\n"
            ),
            stderr="",
        )

    command = ListSystemServicesCommand(
        executable_finder=find_executable,
        command_runner=run_command,
    )

    services, manager, errors = command._collect_windows_services()

    assert services[0]["status"] == "stopped"
    assert manager == "Windows Service Control Manager (sc.exe)"
    assert errors == [
        "PowerShell Get-Service returned an unexpected JSON shape."
    ]
