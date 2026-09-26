#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Regression tests for the public QZX command contract."""

import json
import shlex
import zipfile

from qzx.commands.file.create_directory import CreateDirectoryCommand
from qzx.commands.file.delete_path import DeletePathCommand
from qzx.commands.system.run_diagnostic_command import RunDiagnosticCommand
from qzx.commands.system.run_script import RunScriptCommand
from qzx.cli import QZX, _parse_cli_request
from qzx.core.command_base import CommandBase
from qzx.core.command_loader import CommandLoader
from cli_contract_support import DangerousFixtureCommand, _run_cli


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


def test_variadic_option_passthrough_is_explicit_and_literal_dash_values_use_marker():
    valid, values, error = CreateDirectoryCommand().parse_arguments(["--parth"])

    assert valid is False
    assert values is None
    assert error["error_code"] == "usage_error"
    assert "Use '--' before a literal value" in error["error"]

    valid, values, error = CreateDirectoryCommand().parse_arguments(
        ["--", "--literal-directory"]
    )

    assert valid is True
    assert error is None
    assert values["directory_paths"] == ["--literal-directory"]

    valid, values, error = RunDiagnosticCommand().parse_arguments(
        ["uname", "-a"]
    )
    assert valid is True
    assert error is None
    assert values["args"] == ["-a"]

    valid, values, error = RunScriptCommand().parse_arguments(
        ["script.py", "--verbose", "-x"]
    )
    assert valid is True
    assert error is None
    assert values["args"] == ["--verbose", "-x"]


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
    assert "Welcome to QZX - Quick Zap Exchange" in result["output"]
    assert result["onboarding"][0]["stage"] == "first_success"
    assert result["onboarding"][0]["command"].endswith("--json")
    assert result["documentation_url"].endswith("/en/commands")
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
