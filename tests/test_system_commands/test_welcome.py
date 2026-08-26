"""Startup-focused tests for the QZX welcome presentation."""

import json
from importlib.resources import files

import pytest

from qzx import __version__
from qzx._build_info import ATTRIBUTION, ONBOARDING
from qzx.commands.system.terminal_welcome import TerminalWelcome
from qzx.commands.system.welcome import WelcomeCommand
from qzx.fast_startup import main as fast_startup_main
from qzx.welcome_text import (
    COMMAND_CATALOG_URL,
    SECURITY_GUIDE_URL,
    WELCOME_BORDER,
    basic_welcome_message,
    onboarding_plan,
)


def test_packaged_onboarding_contract_drives_every_runtime_projection():
    manifest = json.loads(
        files("qzx")
        .joinpath("resources", "product-manifest.json")
        .read_text(encoding="utf-8")
    )

    assert ONBOARDING == manifest["onboarding"]
    assert COMMAND_CATALOG_URL == manifest["urls"][
        ONBOARDING["documentation_url_key"]
    ]
    assert SECURITY_GUIDE_URL == manifest["urls"][ONBOARDING["security_url_key"]]
    assert [step["stage"] for step in ONBOARDING["steps"]] == [
        "first_success",
        "explore",
        "understand",
    ]
    assert [step["command"] for step in onboarding_plan()] == [
        "qzx getCurrentDateTime --output-format iso --json",
        "qzx listCommands file",
        "qzx help findFiles",
    ]
    assert onboarding_plan(language="es")[0]["purpose"] == (
        ONBOARDING["steps"][0]["purpose"]["es"]
    )


def test_fast_and_regular_basic_welcome_share_canonical_text():
    message = TerminalWelcome(qzx_version="test").get_welcome_message()

    assert message == basic_welcome_message("test")
    assert "Welcome to QZX - Quick Zap Exchange" in message
    assert "FIRST SUCCESS (read-only)" in message
    assert "qzx getCurrentDateTime --output-format iso --json" in message
    assert "qzx listCommands file" in message
    assert "qzx help findFiles" in message
    assert COMMAND_CATALOG_URL in message
    assert SECURITY_GUIDE_URL in message
    assert "Professor" not in message
    assert "WonderMyEnvironment" not in message


def test_interactive_welcome_uses_terminal_ready_instructions():
    message = TerminalWelcome(
        qzx_version="test",
        interactive=True,
    ).get_welcome_message()

    assert "getCurrentDateTime --output-format iso" in message
    assert "listCommands file" in message
    assert "help findFiles" in message
    assert "Type 'exit' or press Ctrl+D." in message
    assert "qzx getCurrentDateTime" not in message
    assert " --json" not in message


def test_fast_startup_claims_attribution_once(tmp_path, capsys):
    environment = {
        "QZX_STATE_DIR": str(tmp_path),
        "QZX_TELEMETRY": "0",
    }

    assert fast_startup_main(environment) == 0
    first_output = capsys.readouterr()
    assert ATTRIBUTION in first_output.out
    assert "Welcome to QZX - Quick Zap Exchange" in first_output.out
    assert "Output:" not in first_output.out
    assert "Details:" not in first_output.out
    assert "Command Maturity" not in first_output.out
    assert first_output.err == ""

    assert fast_startup_main(environment) == 0
    second_output = capsys.readouterr()
    assert ATTRIBUTION not in second_output.out
    assert "Welcome to QZX - Quick Zap Exchange" in second_output.out
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
    assert "Welcome to QZX - Quick Zap Exchange" in output.out
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

    assert "Welcome to QZX - Quick Zap Exchange" in message
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
    assert "Welcome to QZX - Quick Zap Exchange" in result["output"]
    assert result["onboarding"] == onboarding_plan()
    assert result["onboarding"][0]["stage"] == "first_success"
    assert result["onboarding"][0]["risk"] == "read_only"
    assert result["documentation_url"] == COMMAND_CATALOG_URL
    assert result["safety"]["documentation_url"] == SECURITY_GUIDE_URL


@pytest.mark.parametrize(
    ("full_info", "expected_level"),
    [
        (True, "detailed"),
        ("yes", "detailed"),
        (False, "basic"),
        ("off", "basic"),
    ],
)
def test_welcome_uses_the_shared_strict_boolean_contract(
    full_info,
    expected_level,
):
    result = WelcomeCommand().execute(full_info)

    assert result["success"] is True
    assert result["info_level"] == expected_level


def test_welcome_rejects_unknown_boolean_values():
    result = WelcomeCommand().execute("perhaps")

    assert result == {
        "success": False,
        "message": "full_info must be true or false.",
        "error": "Invalid full_info value.",
        "error_code": "invalid_full_info",
        "welcome_displayed": False,
    }


def test_welcome_failure_does_not_disclose_internal_exception_text():
    def broken_factory(**kwargs):
        raise RuntimeError("private path and upstream response")

    result = WelcomeCommand(welcome_factory=broken_factory).execute()

    assert result["success"] is False
    assert result["error_code"] == "welcome_presentation_failed"
    assert result["exception_type"] == "RuntimeError"
    assert "private path" not in json.dumps(result)
    assert "upstream response" not in json.dumps(result)


def test_basic_welcome_does_not_import_optional_psutil():
    def unexpected_optional_import():
        raise AssertionError("basic welcome must not import psutil")

    message = TerminalWelcome(
        psutil_loader=unexpected_optional_import,
    ).get_welcome_message()

    assert "Welcome to QZX - Quick Zap Exchange" in message
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
    assert "DETAILED SYSTEM SNAPSHOT (explicitly requested)" in message
    assert message.count(WELCOME_BORDER) == 3
    assert "System\n------\nOperating System: FixtureOS 1" in message
    assert "Memory\n------\nTotal: 1.00 KB" in message
    assert "Storage\n-------\nfixture (/fixture)" in message
