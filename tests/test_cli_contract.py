#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Regression tests for the public QZX command contract."""

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
import zipfile

from qzx.commands.file.delete_path import DeletePathCommand
from qzx.commands.system.list_disk_devices import ListDiskDevicesCommand
from qzx.commands.system.terminal import QZXTerminal
from qzx.cli import (
    QZX,
    _json_compatible,
    _parse_cli_request,
    _render_human,
)
from qzx.core.command_base import CommandBase
from qzx.core.command_loader import CommandLoader


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class DangerousFixtureCommand(CommandBase):
    name = "dangerousFixture"
    maturity = "alpha"
    description = "Test-only high-risk command"
    requires_explicit_approval = True
    backup_target_parameter = "target"
    parameters = [
        {
            "name": "target",
            "description": "Test backup target",
            "required": True,
            "type": "str",
        },
    ]
    examples = []

    def __init__(self):
        self.executions = 0

    def execute(self, target):
        self.executions += 1
        return {"success": True, "message": "executed"}


class RichFixtureCommand(CommandBase):
    name = "richFixture"
    maturity = "alpha"
    description = "Test-only rich command"
    parameters = []
    examples = []

    def execute(self):
        return {
            "success": True,
            "message": "Fixture inspection completed.",
            "details": {
                "items_found": 2,
                "ready": True,
            },
        }


def _run_cli(*arguments, environment_overrides=None):
    environment = os.environ.copy()
    environment["QZX_TELEMETRY"] = "0"
    environment["PYTHONPATH"] = str(REPOSITORY_ROOT / "src")
    environment.update(environment_overrides or {})
    return subprocess.run(
        [sys.executable, "-m", "qzx", *arguments],
        cwd=REPOSITORY_ROOT,
        env=environment,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )


def test_shared_boolean_parser_accepts_only_explicit_boolean_values():
    accepted = {
        True: True,
        False: False,
        "true": True,
        "YES": True,
        "1": True,
        "on": True,
        "t": True,
        "false": False,
        "NO": False,
        "0": False,
        "off": False,
        "f": False,
    }
    for raw_value, expected in accepted.items():
        assert CommandBase._parse_bool(raw_value) is expected

    for raw_value in (None, 1, 0, [], {}, "sometimes", ""):
        assert CommandBase._parse_bool(raw_value) is None


def test_discovery_is_complete_and_collision_free():
    loader = CommandLoader()
    commands = loader.discover_commands()

    assert len(set(commands.values())) >= 80
    assert loader.load_errors == {}
    assert loader.registration_warnings == []
    assert loader.attempted_installs == set()


def test_default_welcome_uses_lazy_index_without_full_discovery():
    runtime = QZX()

    result = runtime.execute("welcome", [])

    assert result["success"] is True
    assert "Welcome Professor!" in result["output"]
    assert runtime.command_loader._discovered is False
    assert set(runtime.command_loader.command_modules) == {
        "qzx.commands.system.welcome",
    }


def test_default_welcome_omits_detailed_operating_system_payload():
    result = QZX().execute("welcome", [])

    assert result["success"] is True
    assert result["info_level"] == "basic"
    assert "system_info" not in result


def test_every_documented_example_resolves_and_parses():
    loader = CommandLoader()
    registered = loader.discover_commands()

    failures = []
    for command_class in sorted(
        set(registered.values()),
        key=lambda item: item.name.lower(),
    ):
        command = command_class()
        for example in command.examples:
            tokens = shlex.split(example["command"], posix=True)
            if len(tokens) < 2 or tokens[0].lower() != "qzx":
                failures.append((command.name, example["command"], "missing qzx prefix"))
                continue
            _json_output, parsed_name, parsed_args = _parse_cli_request(
                tokens[1:]
            )
            resolved_class = registered.get(parsed_name.lower())
            if resolved_class is None:
                failures.append((command.name, example["command"], "unknown command"))
                continue
            valid, _values, error = resolved_class().parse_arguments(parsed_args)
            if not valid:
                failures.append((command.name, example["command"], error["error"]))

    assert failures == []


def test_dangerous_commands_back_up_by_default_and_flags_bypass(
    tmp_path,
    monkeypatch,
):
    target = tmp_path / "target"
    target.mkdir()
    (target / "data.txt").write_text("before", encoding="utf-8")
    backup_directory = tmp_path / "backups"
    monkeypatch.delenv("QZX_SAFETY", raising=False)
    monkeypatch.setenv("QZX_BACKUPS_PATH", str(backup_directory))
    monkeypatch.delenv("QZX_BACKUPS_FORMAT", raising=False)
    monkeypatch.delenv("QZX_BACKUPS_COMPRESSION", raising=False)
    command = DangerousFixtureCommand()

    protected = command.invoke([str(target)])
    backup_files = list(backup_directory.glob("*.zip"))

    bypassed = command.invoke([str(target), "--yolo"])
    long_bypassed = command.invoke(
        [
            str(target),
            "--dangerously-bypass-approvals-and-sandbox",
        ]
    )

    assert protected["success"] is True
    assert protected["meta"]["safety_backup"]["status"] == "created"
    assert len(backup_files) == 1
    with zipfile.ZipFile(backup_files[0]) as archive:
        assert "target/data.txt" in archive.namelist()
    assert bypassed["success"] is True
    assert bypassed["meta"]["safety_backup"]["status"] == "bypassed"
    assert long_bypassed["success"] is True
    assert len(list(backup_directory.glob("*.zip"))) == 1
    assert command.executions == 3


def test_dangerous_command_stops_when_backup_configuration_is_invalid(
    tmp_path,
    monkeypatch,
):
    target = tmp_path / "target"
    target.mkdir()
    monkeypatch.delenv("QZX_SAFETY", raising=False)
    monkeypatch.setenv("QZX_BACKUPS_PATH", str(tmp_path / "backups"))
    monkeypatch.setenv("QZX_BACKUPS_FORMAT", "7Z")
    command = DangerousFixtureCommand()

    result = command.invoke([str(target)])

    assert result["success"] is False
    assert result["error_code"] == "safety_backup_failed"
    assert result["meta"]["safety_backup"]["status"] == "failed"
    assert command.executions == 0


def test_delete_path_is_preview_first_and_default_execution_is_backed_up(
    tmp_path,
    monkeypatch,
):
    target = tmp_path / "disposable.txt"
    target.write_text("temporary", encoding="utf-8")
    backup_directory = tmp_path / "backups"
    monkeypatch.delenv("QZX_SAFETY", raising=False)
    monkeypatch.setenv("QZX_BACKUPS_PATH", str(backup_directory))
    command = DeletePathCommand()

    preview = command.invoke([str(target)])
    assert preview["success"] is True
    assert preview["details"]["dry_run_mode"] is True
    assert target.exists()
    assert not backup_directory.exists()

    deleted = command.invoke(
        [
            str(target),
            "--dry_run",
            "false",
            "--apply",
        ]
    )
    assert deleted["success"] is True
    assert deleted["details"]["dry_run_mode"] is False
    assert not target.exists()
    backup_files = list(backup_directory.glob("*.zip"))
    assert len(backup_files) == 1
    with zipfile.ZipFile(backup_files[0]) as archive:
        assert archive.read("disposable.txt") == b"temporary"


def test_recursive_option_consumes_only_explicit_boolean_or_depth_value():
    command = DeletePathCommand()

    valid_boolean, boolean_values, boolean_error = command.parse_arguments(
        ["target", "--recursive", "true", "--force", "false"]
    )
    valid_depth, depth_values, depth_error = command.parse_arguments(
        ["target", "--recursive", "2"]
    )
    valid_flag, flag_values, flag_error = command.parse_arguments(
        ["target", "-r"]
    )

    assert valid_boolean is True
    assert boolean_error is None
    assert boolean_values["recursive"] is True
    assert boolean_values["force"] is False
    assert valid_depth is True
    assert depth_error is None
    assert depth_values["recursive"] == 2
    assert valid_flag is True
    assert flag_error is None
    assert flag_values["recursive"] == "-r"


def test_boolean_defaults_reject_ambiguous_cli_text():
    valid, values, error = DeletePathCommand().parse_arguments(
        ["target", "--force", "perhaps"]
    )

    assert valid is False
    assert values is None
    assert error["error_code"] == "usage_error"
    assert "expected true/false for 'force'" in error["message"]


def test_delete_path_short_recursive_flag_removes_descendants(tmp_path):
    target = tmp_path / "disposable"
    target.mkdir()
    (target / "nested.txt").write_text("temporary", encoding="utf-8")

    result = DeletePathCommand().invoke(
        [str(target), "-r", "--dry-run", "false", "--apply", "--yolo"]
    )

    assert result["success"] is True
    assert result["details"]["recursive"] is True
    assert not target.exists()


def test_qzx_safety_yolo_is_honored_by_the_public_cli(
    tmp_path,
    monkeypatch,
):
    target = tmp_path / "disposable.txt"
    target.write_text("temporary", encoding="utf-8")
    backup_directory = tmp_path / "backups"
    monkeypatch.setenv("QZX_SAFETY", "YOLO")
    monkeypatch.setenv("QZX_BACKUPS_PATH", str(backup_directory))

    completed = _run_cli("deletePath", str(target), "--json")
    payload = json.loads(completed.stdout)

    assert completed.returncode == 0
    assert payload["success"] is True
    assert payload["meta"]["safety_backup"]["reason"] == "QZX_SAFETY=YOLO"
    assert not target.exists()
    assert not backup_directory.exists()


def test_json_mode_emits_one_document_and_failure_exit_code(tmp_path):
    missing_file = tmp_path / "missing.txt"
    completed = _run_cli("readFile", str(missing_file), "--json")

    payload = json.loads(completed.stdout)
    assert completed.returncode == 1
    assert payload["success"] is False
    assert payload["error_code"] == "file_not_found"


def test_json_mode_captures_native_child_output_before_serializing():
    completed = _run_cli("clearScreen", "--json")

    payload = json.loads(completed.stdout)
    assert completed.returncode == 0
    assert completed.stdout.startswith("{")
    assert payload["success"] is True
    assert payload["screen_cleared"] is True


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
