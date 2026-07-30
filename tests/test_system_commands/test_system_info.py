"""Behavioral tests for the consolidated system-information contract."""

from qzx import __version__
from qzx.commands.system.get_environment_info import (
    WonderMyEnvironmentCommand,
)
from qzx.commands.system.system_info import SystemInfoCommand
from qzx.core.command_lifecycle import command_maturity


def test_basic_system_info_is_structured_and_avoids_optional_probes():
    def unexpected_probe():
        raise AssertionError("basic systemInfo must not run detailed probes")

    result = SystemInfoCommand(
        details_collector=unexpected_probe
    ).execute()

    assert result["success"] is True
    assert result["details_requested"] is False
    assert result["environment_included"] is False
    assert result["system_info"]["qzx"]["version"] == __version__
    assert "memory" not in result["system_info"]
    assert "storage" not in result["system_info"]
    assert (
        "environment_variables"
        not in result["system_info"]["environment"]
    )


def test_environment_values_are_opt_in_and_limited_to_the_allowlist():
    environment = {
        "QZX_SYSTEM_INFO_SECRET_FIXTURE": "must-not-leak",
        "LANG": "qzx-test-language",
    }

    result = SystemInfoCommand(environ=environment).execute(
        include_environment=True
    )

    variables = result["system_info"]["environment"][
        "environment_variables"
    ]
    assert result["environment_included"] is True
    assert variables["LANG"] == "qzx-test-language"
    assert "QZX_SYSTEM_INFO_SECRET_FIXTURE" not in variables
    assert set(variables) <= set(
        SystemInfoCommand._environment_variable_allowlist
    )


def test_detailed_system_info_runs_real_memory_and_storage_probes():
    result = SystemInfoCommand().execute(detailed=True)

    assert result["success"] is True, result
    assert result["details_requested"] is True
    assert result["system_info"]["memory"]["virtual_memory"]["total"] > 0
    assert result["system_info"]["storage"]["summary"]["total_disks"] > 0
    assert "getGPULoad" in result["message"]


def test_system_info_cli_boolean_contract_is_strict():
    result = SystemInfoCommand().invoke(["--detailed=maybe"])

    assert result["success"] is False
    assert result["error_code"] == "usage_error"
    assert "expected true/false" in result["message"]


def test_system_info_direct_boolean_contract_is_structured():
    result = SystemInfoCommand().execute(detailed="maybe")

    assert result["success"] is False
    assert result["error_code"] == "invalid_boolean"
    assert "true or false" in result["message"]


def test_legacy_environment_command_delegates_without_printing(capsys):
    result = WonderMyEnvironmentCommand().execute(detailed=False)

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
    assert result["success"] is True
    assert result["deprecated"] is True
    assert result["replacement"] == "systemInfo"
    assert result["supported_through"] == "QZX 0.2.x"
    assert result["system_info"]["qzx"]["version"] == __version__
    assert "memory" not in result["system_info"]
    assert "storage" not in result["system_info"]


def test_legacy_environment_command_has_a_valid_deprecation_review():
    maturity = command_maturity("getEnvironmentInfo")

    assert maturity["stage"] == "deprecated"
    assert maturity["review"]["replacement"] == "systemInfo"
