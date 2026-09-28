#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Regression tests for public QZX CLI output and terminal rendering."""

import json
import os
import sys
from pathlib import Path

from cli_contract_support import (
    DangerousFixtureCommand,
    RichFixtureCommand,
    _run_cli,
)
from qzx.commands.system.list_disk_devices import ListDiskDevicesCommand
from qzx.commands.system.terminal import QZXTerminal
from qzx.cli import (
    _json_compatible,
    _parse_cli_request,
    _render_human,
    _schedule_optional_telemetry,
)
from qzx.core.command_loader import CommandLoader


def test_json_mode_emits_one_document_and_failure_exit_code(tmp_path):
    missing_file = tmp_path / "missing.txt"
    completed = _run_cli("readFile", str(missing_file), "--json")

    payload = json.loads(completed.stdout)
    assert completed.returncode == 1
    assert payload["success"] is False
    assert payload["error_code"] == "file_not_found"


def test_json_mode_keeps_terminal_control_bytes_out_of_redirected_stdout():
    completed = _run_cli("clearScreen", "--json")

    payload = json.loads(completed.stdout)
    assert completed.returncode == 0
    assert completed.stdout.startswith("{")
    assert "\x1b" not in completed.stdout
    assert payload["success"] is True
    assert payload["screen_cleared"] is False
    assert payload["details"]["reason"] == "non_interactive_output"
    assert payload["details"]["shell_spawned"] is False


def test_json_mode_emits_utf8_bytes_when_stdout_uses_non_utf8_encoding(
    tmp_path,
):
    tree_root = tmp_path / "tree"
    nested = tree_root / "nested"
    nested.mkdir(parents=True)
    (nested / "unicode-λ.txt").write_text("content", encoding="utf-8")

    completed = _run_cli(
        "getProjectTree",
        str(tree_root),
        "2",
        "--json",
        environment_overrides={
            "PYTHONIOENCODING": "cp1252",
            "QZX_STATE_DIR": str(tmp_path / "state"),
        },
        text=False,
    )

    stdout = completed.stdout.decode("utf-8")
    payload = json.loads(stdout)
    assert completed.returncode == 0
    assert payload["success"] is True
    assert "unicode-λ.txt" in payload["tree_text"]
    assert "└──" in payload["tree_text"]


def test_no_argument_module_entrypoint_uses_the_clean_fast_welcome(tmp_path):
    completed = _run_cli(
        environment_overrides={"QZX_STATE_DIR": str(tmp_path)},
    )

    assert completed.returncode == 0
    assert "Welcome to QZX - Quick Zap Exchange" in completed.stdout
    assert "FIRST SUCCESS (read-only)" in completed.stdout
    assert "Output:" not in completed.stdout
    assert "Details:" not in completed.stdout
    assert "Command Maturity" not in completed.stdout


def test_human_stdout_is_utf8_even_when_the_inherited_code_page_is_legacy(
    tmp_path,
):
    completed = _run_cli(
        "about",
        environment_overrides={
            "PYTHONIOENCODING": "cp1252",
            "QZX_STATE_DIR": str(tmp_path),
        },
        text=False,
    )

    stdout = completed.stdout.decode("utf-8", errors="strict")
    assert completed.returncode == 0
    assert "QZX — Quick Zap Exchange" in stdout
    assert "Alejandro Sánchez" in stdout


def test_unknown_command_uses_127_and_suggestions():
    completed = _run_cli("readFil", "--json")

    payload = json.loads(completed.stdout)
    assert completed.returncode == 127
    assert payload["error_code"] == "command_not_found"
    assert "readFile" in payload["details"]["suggestions"]


def test_about_command_and_version_global_flag_include_attribution(tmp_path):
    attribution = (
        "QZX — Quick Zap Exchange, created and maintained by Alejandro Sánchez."
    )
    environment = {"QZX_STATE_DIR": str(tmp_path)}

    about = _run_cli("about", "--json", environment_overrides=environment)
    version = _run_cli("--version", "--json", environment_overrides=environment)
    about_payload = json.loads(about.stdout)
    version_payload = json.loads(version.stdout)

    assert about.returncode == 0
    assert about_payload["attribution"] == attribution
    assert about_payload["license"]["spdx"] == "Apache-2.0"
    assert version.returncode == 0
    assert version_payload["attribution"] == attribution
    assert version_payload["license"] == "Apache-2.0"


def test_help_flag_after_command_uses_the_canonical_help_contract():
    json_output, command, arguments = _parse_cli_request(
        ["findFiles", "--limit", "5", "--help", "--json"]
    )

    assert json_output is True
    assert command == "help"
    assert arguments == ["findFiles"]

    completed = _run_cli("findFiles", "-h", "--json")
    payload = json.loads(completed.stdout)

    assert completed.returncode == 0
    assert payload["success"] is True
    assert payload["details"]["canonical_name"] == "findFiles"
    assert any(
        parameter["name"] == "modified_after"
        for parameter in payload["details"]["parameters"]
    )


def test_first_run_attribution_is_shown_once_without_breaking_json(tmp_path):
    attribution = (
        "QZX — Quick Zap Exchange, created and maintained by Alejandro Sánchez."
    )
    human_state = tmp_path / "human"
    environment = {"QZX_STATE_DIR": str(human_state)}

    first = _run_cli(
        "getCurrentDateTime",
        environment_overrides=environment,
    )
    second = _run_cli(
        "getCurrentDateTime",
        environment_overrides=environment,
    )

    assert first.returncode == 0
    assert first.stdout.startswith(attribution + "\n")
    assert attribution not in second.stdout

    json_state = tmp_path / "json"
    json_first = _run_cli(
        "getCurrentDateTime",
        "--json",
        environment_overrides={"QZX_STATE_DIR": str(json_state)},
    )
    payload = json.loads(json_first.stdout)

    assert json_first.stdout.startswith("{")
    assert payload["meta"]["first_run_attribution"] == attribution


def test_usage_error_uses_exit_code_2():
    completed = _run_cli("readFile", "--max_lines", "5", "--json")

    payload = json.loads(completed.stdout)
    assert completed.returncode == 2
    assert payload["error_code"] == "usage_error"


def test_cli_telemetry_opt_out_skips_heavy_telemetry_imports(monkeypatch):
    monkeypatch.setenv("QZX_TELEMETRY", "0")
    monkeypatch.setenv("DO_NOT_TRACK", "1")
    monkeypatch.delitem(sys.modules, "qzx.telemetry", raising=False)
    monkeypatch.delitem(sys.modules, "qzx.usage_telemetry", raising=False)

    _schedule_optional_telemetry(
        {"success": True, "meta": {"command": "about"}}
    )

    assert "qzx.telemetry" not in sys.modules
    assert "qzx.usage_telemetry" not in sys.modules


def test_legacy_error_text_is_normalized_as_failure():
    result = DangerousFixtureCommand().format_result("Error: legacy failure")

    assert result["success"] is False
    assert result["error_code"] == "legacy_unstructured_error"


def test_list_disk_devices_reports_the_real_current_filesystem():
    disk_path = Path.cwd().anchor or os.path.abspath(os.sep)

    result = ListDiskDevicesCommand().invoke([disk_path])

    assert result["success"] is True
    assert disk_path in result["message"]
    assert result["disks"]
    disk = result["disks"][0]
    assert disk["path"] == disk_path
    assert disk["total"] > 0
    assert disk["used"] >= 0
    assert disk["free"] >= 0
    assert disk["total"] >= disk["free"]
    assert disk["total_readable"]


def test_every_public_command_uses_the_shared_dual_output_contract():
    loader = CommandLoader()
    registered = loader.discover_commands()
    command_classes = sorted(
        set(registered.values()),
        key=lambda command_class: command_class.name.lower(),
    )

    failures = []
    for invocation_name in sorted(registered):
        json_output, parsed_name, parsed_args = _parse_cli_request(
            [invocation_name, "--json"]
        )
        if not json_output or parsed_name != invocation_name or parsed_args:
            failures.append((invocation_name, "global --json parsing"))

    for command_class in command_classes:
        command = command_class()
        normalized = command.format_result(
            {
                "success": True,
                "message": "{} audit result.".format(command.name),
                "details": {"command": command.name, "available": True},
            }
        )
        encoded = json.dumps(
            _json_compatible(normalized),
            ensure_ascii=False,
            allow_nan=False,
        )
        human = _render_human(normalized)

        if json.loads(encoded) != normalized:
            failures.append((command.name, "stable JSON serialization"))
        if (
            not human.startswith(normalized["message"])
            or "{'" in human
            or '"success":' in human
        ):
            failures.append((command.name, "human terminal rendering"))

    assert len(command_classes) >= 80
    assert len(registered) == len(command_classes)
    assert failures == []


def test_human_renderer_preserves_nested_data_without_raw_containers():
    rendered = _render_human(
        {
            "success": True,
            "message": "Workspace scan completed.",
            "details": {
                "files_found": 2,
                "scan_complete": True,
                "items": [
                    {"path": "one.py", "size_bytes": 12},
                    {"path": "two.py", "size_bytes": 34},
                ],
            },
            "meta": {
                "command": "scanFixture",
                "duration_ms": 1.2,
                "schema_version": 1,
                "safety_backup": {
                    "status": "created",
                    "path": "QZX-Backups/example.zip",
                },
            },
        }
    )

    assert "Workspace scan completed." in rendered
    assert "Files Found: 2" in rendered
    assert "Scan Complete: Yes" in rendered
    assert "Path: one.py" in rendered
    assert "Safety Backup:" in rendered
    assert "{'" not in rendered
    assert '"files_found"' not in rendered


def test_human_renderer_flattens_details_and_deduplicates_compatibility_fields():
    external_service = {
        "provider": "Google Gemini",
        "content_shared": False,
    }
    rendered = _render_human(
        {
            "success": True,
            "message": "External request preview is ready.",
            "details": {
                "file_size_bytes": 1024,
                "external_service": external_service,
            },
            # Some commands retain a top-level projection for compatibility.
            "external_service": external_service,
        }
    )

    assert rendered.count("Details:") == 1
    assert "\n  Details:" not in rendered
    assert "File Size Bytes: 1024" in rendered
    assert rendered.count("External Service:") == 1
    assert "Content Shared: No" in rendered


def test_human_renderer_uses_dedicated_content_without_duplicate_structures():
    rendered = _render_human(
        {
            "success": True,
            "message": "Read two lines.",
            "content": "first line\nsecond line",
            "details": {
                "content": "first line\nsecond line",
                "lines_read": 2,
            },
        }
    )

    assert "Content:" in rendered
    assert rendered.count("first line") == 1
    assert "{'" not in rendered


def test_strict_json_normalizes_non_finite_numbers():
    compatible = _json_compatible(
        {
            "success": True,
            "message": "Metrics collected.",
            "metrics": [float("nan"), float("inf"), float("-inf")],
        }
    )
    encoded = json.dumps(compatible, allow_nan=False)

    assert json.loads(encoded)["metrics"] == ["nan", "inf", "-inf"]


def test_interactive_terminal_uses_the_shared_human_and_json_renderers(capsys):
    terminal = object.__new__(QZXTerminal)
    terminal.commands = {"richfixture": RichFixtureCommand}
    terminal._update_prompt = lambda: None

    terminal.default("richFixture")
    human_output = capsys.readouterr().out
    terminal.default("richFixture --json")
    json_output = capsys.readouterr().out

    assert "Fixture inspection completed." in human_output
    assert "Items Found: 2" in human_output
    assert "{'" not in human_output
    assert json.loads(json_output)["details"]["ready"] is True


def test_interactive_terminal_accepts_a_bom_prefixed_piped_command():
    terminal = object.__new__(QZXTerminal)

    normalized = terminal.precmd("\ufeffexit")

    assert normalized == "exit"
    assert terminal.onecmd(normalized) is True
