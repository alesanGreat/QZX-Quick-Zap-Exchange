"""Startup-focused tests for the QZX welcome presentation."""

import pytest

from qzx import __version__
from qzx._build_info import ATTRIBUTION
from qzx.commands.system.terminal_welcome import TerminalWelcome
from qzx.commands.system.welcome import WelcomeCommand
from qzx.fast_startup import main as fast_startup_main
from qzx.welcome_text import basic_welcome_message


def test_fast_and_regular_basic_welcome_share_canonical_text():
    message = TerminalWelcome(qzx_version="test").get_welcome_message()

    assert message == basic_welcome_message("test")
    assert "Type 'systemInfo'" in message
    assert "WonderMyEnvironment" not in message


def test_fast_startup_claims_attribution_once(tmp_path, capsys):
    environment = {
        "QZX_STATE_DIR": str(tmp_path),
        "QZX_TELEMETRY": "0",
    }

    assert fast_startup_main(environment) == 0
    first_output = capsys.readouterr()
    assert ATTRIBUTION in first_output.out
    assert "Welcome Professor!" in first_output.out
    assert first_output.err == ""

    assert fast_startup_main(environment) == 0
    second_output = capsys.readouterr()
    assert ATTRIBUTION not in second_output.out
    assert "Welcome Professor!" in second_output.out
    assert second_output.err == ""


@pytest.mark.parametrize(
    ("debug_value", "expected_error"),
    [
        (None, ""),
        ("true", "QZX telemetry scheduling failed: RuntimeError."),
    ],
)
def test_fast_startup_keeps_telemetry_failures_safe_and_optional(
    tmp_path,
    capsys,
    debug_value,
    expected_error,
):
    def fail_without_leaking_message(*args, **kwargs):
        raise RuntimeError("sensitive upstream response")

    environment = {
        "QZX_STATE_DIR": str(tmp_path),
        "QZX_TELEMETRY": "1",
    }
    if debug_value is not None:
        environment["QZX_TELEMETRY_DEBUG"] = debug_value

    assert (
        fast_startup_main(
            environment,
            telemetry_scheduler=fail_without_leaking_message,
        )
        == 0
    )

    output = capsys.readouterr()
    assert "Welcome Professor!" in output.out
    assert output.err.strip() == expected_error
    assert "sensitive upstream response" not in output.err


def test_welcome_message_does_not_probe_system_resources():
    probes = []

    def collect_system_info():
        probes.append("collected")
        return {"system": "fixture"}

    welcome = TerminalWelcome(
        qzx_version="test",
        system_info_provider=collect_system_info,
    )

    message = welcome.get_welcome_message()

    assert "Welcome Professor!" in message
    assert probes == []
    assert welcome.system_info == {"system": "fixture"}
    assert welcome.system_info == {"system": "fixture"}
    assert probes == ["collected"]


def test_public_welcome_does_not_collect_unused_environment_details():
    def unexpected_probe():
        raise AssertionError("welcome must not inspect disks, RAM, or CPU")

    def welcome_factory(qzx_version):
        return TerminalWelcome(
            qzx_version=qzx_version,
            system_info_provider=unexpected_probe,
        )

    result = WelcomeCommand(welcome_factory=welcome_factory).execute()

    assert result["success"] is True
    assert "Welcome Professor!" in result["output"]


def test_basic_welcome_does_not_import_optional_psutil():
    def unexpected_optional_import():
        raise AssertionError("basic welcome must not import psutil")

    message = TerminalWelcome(
        psutil_loader=unexpected_optional_import,
    ).get_welcome_message()

    assert "Welcome Professor!" in message
    assert f"Version {__version__}" in message


def test_detailed_welcome_collects_once_and_labels_expensive_details():
    probes = []

    def collect_system_info():
        probes.append("collected")
        return {
            "system": "FixtureOS",
            "release": "1",
            "version": "1.0",
            "architecture": "fixture",
            "python_implementation": "CPython",
            "python_version": "3.13.12",
            "ram_total": 1024,
            "ram_used": 512,
            "ram_available": 512,
            "ram_percent": 50,
            "disk_info": [
                {
                    "device": "fixture",
                    "mountpoint": "/fixture",
                    "total": 2048,
                    "used": 1024,
                    "free": 1024,
                    "percent": 50,
                }
            ],
        }

    message = TerminalWelcome(
        qzx_version="test",
        system_info_provider=collect_system_info,
        psutil_loader=lambda: object(),
    ).get_welcome_message(show_full_info=True)

    assert probes == ["collected"]
    assert "System\n------\nOperating System: FixtureOS 1" in message
    assert "Memory\n------\nTotal: 1.00 KB" in message
    assert "Storage\n-------\nfixture (/fixture)" in message
