#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for sanitized Golden Core platform-evidence capture and merging."""

from __future__ import annotations

import getpass
import json
import platform
from pathlib import Path

import pytest

from qzx.core.command_loader import CommandLoader
from scripts.golden_core_platform_assertions import command_assertions
from scripts.capture_golden_core_platform_evidence import (
    replacement_pairs,
    sanitize_value,
    sha256_value,
)
from scripts.merge_golden_core_platform_evidence import (
    merge,
    validate_evidence,
)
from scripts.verify_golden_core import load_golden_core


SOURCE_REVISION = "a" * 40
SCRIPT_ROOT = Path(__file__).resolve().parents[1] / "scripts"


def test_list_commands_assertion_tracks_current_command_index():
    count = len(CommandLoader().get_indexed_commands())
    assertions = command_assertions(
        "listCommands",
        {"summary": {"commands": count}},
    )
    assert f"command_count={count}" in assertions

    with pytest.raises(AssertionError, match=str(count)):
        command_assertions(
            "listCommands",
            {"summary": {"commands": count - 1}},
        )


def evidence_document(system: str, environment_id: str) -> dict:
    commands = [item["name"] for item in load_golden_core()["commands"]]
    document = {
        "schema_version": 2,
        "evidence_type": "qzx_golden_core_platform_run",
        "captured_at": "2026-08-08T00:00:00+00:00",
        "source_revision": SOURCE_REVISION,
        "qzx_version": "0.2.2.0.7a3",
        "result_contract": (
            "https://qzx.yumbale.com/schemas/"
            "result-contract-v1.schema.json"
        ),
        "golden_core": _golden_core_fixture(commands),
        "environment": _environment_fixture(system, environment_id),
        "commands": _command_records(commands, system),
        "summary": _summary_fixture(commands, system),
        "scope": _scope_fixture(),
    }
    document["evidence_sha256"] = sha256_value(document)
    return document


def _command_records(commands, system):
    return {
        command_name: _command_record(command_name, system)
        for command_name in commands
    }


def _command_record(command_name, system):
    result = {
        "success": True,
        "message": f"Observed {command_name} on {system}.",
        "meta": {
            "command": command_name,
            "schema_version": 1,
        },
    }
    return {
        "implementation_digest": "sha256:" + "1" * 64,
        "arguments": [command_name],
        "exit_code": 0,
        "elapsed_ms": 1.0,
        "stderr": "",
        "result_sha256": sha256_value(result),
        "assertions": [
            "exit_code=0",
            "result_contract_v1",
            "success=true",
            f"meta.command={command_name}",
            "fixture_assertion",
        ],
        "result": result,
    }


def _golden_core_fixture(commands):
    return {
        "name": "QZX Golden Core",
        "status": "candidate",
        "selected_on": "2026-08-08",
        "command_count": len(commands),
        "commands": commands,
    }


def _environment_fixture(system, environment_id):
    return {
        "id": environment_id,
        "name": f"{system} test environment",
        "system": system,
        "release": "test-release",
        "version": "test-version",
        "machine": "test-machine",
        "processor": "test-processor",
        "python": {
            "implementation": "CPython",
            "version": "3.13.12",
            "architecture": "64bit",
        },
        "github": {},
    }


def _summary_fixture(commands, system):
    return {
        "command_count": len(commands),
        "passed": len(commands),
        "failed": 0,
        "systems_observed": [system],
    }


def _scope_fixture():
    return {
        "success_only": True,
        "network": "authorized loopback HTTP only",
        "repository": "disposable local Git fixture only",
        "secrets": (
            "environment values and private project data are not requested"
        ),
        "claim": "Observed evidence only.",
    }


def write_document(path: Path, document: dict) -> Path:
    path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def test_evidence_cli_writers_force_utf8_lf_bytes():
    for filename in (
        "capture_golden_core_platform_evidence.py",
        "merge_golden_core_platform_evidence.py",
    ):
        source = (SCRIPT_ROOT / filename).read_text(encoding="utf-8")
        assert "arguments.output.write_bytes(" in source
        assert "arguments.output.write_text(" not in source
        assert '(json.dumps(document, ensure_ascii=False, indent=2) + "\\n")' in source


def test_sanitizer_removes_private_identity_paths_and_ephemeral_ports(tmp_path):
    private_path = tmp_path / getpass.getuser() / "fixture"
    value = {
        "path": str(private_path),
        "home": str(Path.home()),
        "hostname": platform.node(),
        "url": "http://127.0.0.1:49152/ok",
    }

    sanitized = sanitize_value(value, replacement_pairs(tmp_path))
    encoded = json.dumps(sanitized, ensure_ascii=False)

    assert str(tmp_path) not in encoded
    assert str(Path.home()) not in encoded
    sanitized_path = str(sanitized["path"]).replace("\\", "/")
    assert f"/{getpass.getuser()}/" not in sanitized_path
    if platform.node():
        assert platform.node() not in encoded
    assert "<fixture-root>" in encoded
    assert "<home>" in encoded
    assert "<hostname>" in encoded
    assert "http://127.0.0.1:<ephemeral-port>/ok" in encoded


def test_sanitizer_never_rewrites_inserted_placeholders():
    sanitized = sanitize_value(
        {"path": "/tmp/qzx-evidence/root/fixture"},
        [
            ("/tmp/qzx-evidence", "<fixture-root>"),
            ("/root", "<home>"),
            ("root", "<user>"),
        ],
    )

    assert sanitized == {"path": "<fixture-root><home>/fixture"}
    assert "<fixture-<user>>" not in sanitized["path"]


def test_merge_accepts_three_declared_systems(tmp_path):
    files = _platform_evidence_files(tmp_path)
    renamed_files = _renamed_evidence_files(tmp_path, files)

    summary = merge(files)
    assert summary == merge(list(reversed(files)))
    assert summary == merge(renamed_files)
    _assert_environment_summary(summary)
    _assert_run_summary(summary)
    _assert_command_summary(summary)
    _assert_aggregate_hash(summary)


def _platform_evidence_files(tmp_path):
    return [
        write_document(
            tmp_path / "windows.json",
            evidence_document("Windows", "windows-2025-x64"),
        ),
        write_document(
            tmp_path / "linux.json",
            evidence_document("Linux", "ubuntu-24.04-x64"),
        ),
        write_document(
            tmp_path / "darwin.json",
            evidence_document("Darwin", "macos-15-arm64"),
        ),
    ]


def _renamed_evidence_files(tmp_path, files):
    directory = tmp_path / "renamed"
    directory.mkdir()
    return [
        write_document(
            directory / f"record-{index}.json",
            json.loads(path.read_text(encoding="utf-8")),
        )
        for index, path in enumerate(reversed(files), start=1)
    ]


def _assert_environment_summary(summary):
    assert [
        environment["source_file"]
        for environment in summary["environments"]
    ] == [
        "macos-15-arm64.json",
        "ubuntu-24.04-x64.json",
        "windows-2025-x64.json",
    ]
    assert summary["generated_at"] == "2026-08-08T00:00:00+00:00"
    assert summary["evidence_window"] == {
        "first_captured_at": "2026-08-08T00:00:00+00:00",
        "last_captured_at": "2026-08-08T00:00:00+00:00",
    }
    assert summary["evidence_type"] == "qzx_golden_core_platform_summary"
    assert summary["source_revision"] == SOURCE_REVISION


def _assert_run_summary(summary):
    run = summary["summary"]
    assert run["environment_count"] == 3
    assert run["system_counts"] == {
        "Darwin": 1,
        "Linux": 1,
        "Windows": 1,
    }
    assert run["command_count"] == 15
    assert run["command_environment_runs"] == 45
    assert run["failed_command_runs"] == 0
    assert summary["requirements"]["declared_systems_observed"] is True


def _assert_command_summary(summary):
    assert all(
        command["declared_systems_observed"] is True
        for command in summary["commands"].values()
    )
    assert all(
        command["implementation_digest"] == "sha256:" + "1" * 64
        for command in summary["commands"].values()
    )


def _assert_aggregate_hash(summary):
    payload = dict(summary)
    observed_hash = payload.pop("aggregate_sha256")
    assert observed_hash == sha256_value(payload)


def test_merge_rejects_a_missing_declared_system(tmp_path):
    files = [
        write_document(
            tmp_path / "windows.json",
            evidence_document("Windows", "windows-2025-x64"),
        ),
        write_document(
            tmp_path / "linux.json",
            evidence_document("Linux", "ubuntu-24.04-x64"),
        ),
    ]

    with pytest.raises(ValueError, match="Darwin"):
        merge(files)


def test_merge_rejects_cross_environment_implementation_drift(tmp_path):
    windows = evidence_document("Windows", "windows-2025-x64")
    linux = evidence_document("Linux", "ubuntu-24.04-x64")
    darwin = evidence_document("Darwin", "macos-15-arm64")
    linux["commands"]["version"]["implementation_digest"] = (
        "sha256:" + "2" * 64
    )
    linux["evidence_sha256"] = sha256_value(
        {key: value for key, value in linux.items() if key != "evidence_sha256"}
    )
    files = [
        write_document(tmp_path / "windows.json", windows),
        write_document(tmp_path / "linux.json", linux),
        write_document(tmp_path / "darwin.json", darwin),
    ]

    with pytest.raises(ValueError, match="implementation digests for version"):
        merge(files)


def test_validation_rejects_a_modified_command_result(tmp_path):
    path = write_document(
        tmp_path / "evidence.json",
        evidence_document("Linux", "ubuntu-24.04-x64"),
    )
    document = json.loads(path.read_text(encoding="utf-8"))
    document["commands"]["version"]["result"]["message"] = "tampered"
    document["evidence_sha256"] = sha256_value(
        {key: value for key, value in document.items() if key != "evidence_sha256"}
    )

    with pytest.raises(ValueError, match="version result hash"):
        validate_evidence(path, document)
