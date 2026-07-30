"""Tests for bounded, structured smartctl disk-health queries."""

import os
from types import SimpleNamespace
import subprocess

from qzx.commands.system.get_disk_health import GetDiskHealthCommand


def _completed(returncode=0, stdout="", stderr=""):
    return SimpleNamespace(
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def test_health_query_uses_exact_binary_and_linux_device():
    observed = {}

    def runner(argv, **kwargs):
        observed["argv"] = argv
        observed["kwargs"] = kwargs
        return _completed(stdout="SMART overall-health: PASSED\n")

    result = GetDiskHealthCommand(
        system_name=lambda: "Linux",
        path_lookup=lambda _: "/usr/sbin/smartctl",
        runner=runner,
    ).execute("nvme0n1")

    assert result["success"] is True
    assert result["health_status"] == "PASSED"
    assert observed["argv"] == [
        os.path.abspath("/usr/sbin/smartctl"),
        "-H",
        "/dev/nvme0n1",
    ]
    assert observed["kwargs"]["shell"] is False
    assert observed["kwargs"]["timeout"] == 15.0


def test_full_windows_query_parses_json_and_uses_view_parameter():
    result = GetDiskHealthCommand(
        system_name=lambda: "Windows",
        path_lookup=lambda _: r"C:\tools\smartctl.exe",
        runner=lambda *args, **kwargs: _completed(
            stdout='{"smart_status": {"passed": true}}'
        ),
    ).execute("PhysicalDrive0", "full")

    assert result["success"] is True
    assert result["device"] == r"\\.\PhysicalDrive0"
    assert result["view"] == "full"
    assert result["smart_data"]["smart_status"]["passed"] is True


def test_health_warning_exit_bits_preserve_a_valid_observation():
    result = GetDiskHealthCommand(
        system_name=lambda: "Darwin",
        path_lookup=lambda _: "/usr/local/sbin/smartctl",
        runner=lambda *args, **kwargs: _completed(
            returncode=1 << 3,
            stdout="SMART overall-health: FAILED\n",
        ),
    ).execute("disk0")

    assert result["success"] is True
    assert result["health_status"] == "FAILED"
    assert result["smartctl_status_flags"] == ["disk_failing"]
    assert result["warnings"][0]["code"] == "smartctl_status_flags"


def test_parse_or_device_open_errors_fail_closed():
    result = GetDiskHealthCommand(
        system_name=lambda: "Linux",
        path_lookup=lambda _: "/usr/sbin/smartctl",
        runner=lambda *args, **kwargs: _completed(
            returncode=2,
            stderr="device open failed",
        ),
    ).execute("sda")

    assert result["success"] is False
    assert result["error_code"] == "smartctl_query_failed"
    assert result["smartctl_status_flags"] == [
        "device_open_or_identification_failed"
    ]


def test_failed_smart_command_or_checksum_fails_closed():
    result = GetDiskHealthCommand(
        system_name=lambda: "Linux",
        path_lookup=lambda _: "/usr/sbin/smartctl",
        runner=lambda *args, **kwargs: _completed(
            returncode=4,
            stdout="partial data",
        ),
    ).execute("sda")

    assert result["success"] is False
    assert result["error_code"] == "smartctl_query_failed"
    assert result["smartctl_status_flags"] == [
        "smart_command_or_checksum_failed"
    ]


def test_missing_smartctl_and_invalid_inputs_are_structured():
    missing = GetDiskHealthCommand(
        system_name=lambda: "Linux",
        path_lookup=lambda _: None,
    ).execute("sda")
    invalid_disk = GetDiskHealthCommand().execute("../sda")
    invalid_view = GetDiskHealthCommand().execute("sda", "json")

    assert missing["error_code"] == "smartctl_not_found"
    assert invalid_disk["error_code"] == "invalid_disk"
    assert invalid_view["error_code"] == "invalid_view"


def test_smartctl_timeout_is_reported_without_traceback():
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])

    result = GetDiskHealthCommand(
        system_name=lambda: "Linux",
        path_lookup=lambda _: "/usr/sbin/smartctl",
        runner=timeout,
    ).execute("sda")

    assert result["success"] is False
    assert result["error_code"] == "smartctl_timeout"
