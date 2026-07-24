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

from qzx.commands.file.delete_file import DeleteFileCommand
from qzx.commands.system.commands_bridge import CommandsBridgeCommand
from qzx.commands.system.get_disk_name import GetDiskNameCommand
from qzx.commands.system.get_today import WonderTodayCommand
from qzx.commands.system.generate_content import WonderContentGenCommand
from qzx.commands.system.terminal import QZXTerminal
from qzx.cli import _json_compatible, _parse_cli_request, _render_human
from qzx.core.command_base import CommandBase
from qzx.core.command_loader import CommandLoader


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class DangerousFixtureCommand(CommandBase):
    name = "dangerousFixture"
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


def test_discovery_is_complete_and_collision_free():
    loader = CommandLoader()
    commands = loader.discover_commands()

    assert len(set(commands.values())) >= 90
    assert loader.load_errors == {}
    assert loader.registration_warnings == []
    assert loader.attempted_installs == set()


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
            resolved_class = registered.get(tokens[1].lower())
            if resolved_class is None:
                failures.append((command.name, example["command"], "unknown command"))
                continue
            valid, _values, error = resolved_class().parse_arguments(tokens[2:])
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


def test_delete_file_is_preview_first_and_default_execution_is_backed_up(
    tmp_path,
    monkeypatch,
):
    target = tmp_path / "disposable.txt"
    target.write_text("temporary", encoding="utf-8")
    backup_directory = tmp_path / "backups"
    monkeypatch.delenv("QZX_SAFETY", raising=False)
    monkeypatch.setenv("QZX_BACKUPS_PATH", str(backup_directory))
    command = DeleteFileCommand()

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


def test_qzx_safety_yolo_is_honored_by_the_public_cli(
    tmp_path,
    monkeypatch,
):
    target = tmp_path / "disposable.txt"
    target.write_text("temporary", encoding="utf-8")
    backup_directory = tmp_path / "backups"
    monkeypatch.setenv("QZX_SAFETY", "YOLO")
    monkeypatch.setenv("QZX_BACKUPS_PATH", str(backup_directory))

    completed = _run_cli("deleteFile", str(target), "--json")
    payload = json.loads(completed.stdout)

    assert completed.returncode == 0
    assert payload["success"] is True
    assert payload["meta"]["safety_backup"]["reason"] == "QZX_SAFETY=YOLO"
    assert not target.exists()
    assert not backup_directory.exists()


def test_commands_bridge_blocks_mutating_programs():
    result = CommandsBridgeCommand().invoke(["rm", "-rf", "anything"])

    assert result["success"] is False
    assert result["error_code"] == "command_blocked"


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
    assert "readfile" in payload["details"]["suggestions"]


def test_about_and_version_global_flags_include_attribution(tmp_path):
    attribution = (
        "QZX — Quick Zap Exchange, created and maintained by Alejandro Sánchez."
    )
    environment = {"QZX_STATE_DIR": str(tmp_path)}

    about = _run_cli("--about", "--json", environment_overrides=environment)
    version = _run_cli("--version", "--json", environment_overrides=environment)
    about_payload = json.loads(about.stdout)
    version_payload = json.loads(version.stdout)

    assert about.returncode == 0
    assert about_payload["attribution"] == attribution
    assert about_payload["license"]["spdx"] == "Apache-2.0"
    assert version.returncode == 0
    assert version_payload["attribution"] == attribution
    assert version_payload["license"] == "Apache-2.0"


def test_first_run_attribution_is_shown_once_without_breaking_json(tmp_path):
    attribution = (
        "QZX — Quick Zap Exchange, created and maintained by Alejandro Sánchez."
    )
    human_state = tmp_path / "human"
    environment = {"QZX_STATE_DIR": str(human_state)}

    first = _run_cli(
        "getCurrentDate",
        environment_overrides=environment,
    )
    second = _run_cli(
        "getCurrentDate",
        environment_overrides=environment,
    )

    assert first.returncode == 0
    assert first.stdout.startswith(attribution + "\n")
    assert attribution not in second.stdout

    json_state = tmp_path / "json"
    json_first = _run_cli(
        "getCurrentDate",
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


def test_aliases_are_not_overwritten():
    assert "WonderToday" in WonderTodayCommand.aliases
    assert "WonderContentGen" in WonderContentGenCommand.aliases
    assert "explainfile" in WonderContentGenCommand.aliases


def test_legacy_error_text_is_normalized_as_failure():
    result = DangerousFixtureCommand().format_result("Error: legacy failure")

    assert result["success"] is False
    assert result["error_code"] == "legacy_unstructured_error"


def test_get_disk_name_returns_a_descriptive_structured_success(monkeypatch):
    command = GetDiskNameCommand()
    monkeypatch.setattr(
        "qzx.commands.system.get_disk_name.platform.system",
        lambda: "Windows",
    )
    monkeypatch.setattr(
        "qzx.commands.system.get_disk_name.os.path.exists",
        lambda _path: True,
    )
    monkeypatch.setattr(
        command,
        "_get_disk_info",
        lambda disk_path, _os_type: {
            "path": disk_path,
            "total": 1024,
            "total_readable": "1.00 KB",
        },
    )

    result = command.invoke(["X:\\"])

    assert result["success"] is True
    assert "X:\\" in result["message"]
    assert result["disks"][0]["total_readable"] == "1.00 KB"


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

    assert len(command_classes) >= 90
    assert len(registered) >= 180
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
