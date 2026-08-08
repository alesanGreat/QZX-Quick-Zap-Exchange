#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for sanitized Golden Core platform-evidence capture and merging."""

from __future__ import annotations

import getpass
import json
import platform
from pathlib import Path

import pytest

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


def evidence_document(system: str, environment_id: str) -> dict:
    commands = [item["name"] for item in load_golden_core()["commands"]]
    command_records = {}
    for command_name in commands:
        result = {
            "success": True,
            "message": f"Observed {command_name} on {system}.",
            "meta": {
                "command": command_name,
                "schema_version": 1,
            },
        }
        command_records[command_name] = {
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

    document = {
        "schema_version": 1,
        "evidence_type": "qzx_golden_core_platform_run",
        "captured_at": "2026-08-08T00:00:00+00:00",
        "source_revision": SOURCE_REVISION,
        "qzx_version": "0.2.2.0.7a1",
        "result_contract": (
            "https://qzx.yumbale.com/schemas/"
            "result-contract-v1.schema.json"
        ),
        "golden_core": {
            "name": "QZX Golden Core",
            "status": "candidate",
            "selected_on": "2026-08-08",
            "command_count": len(commands),
            "commands": commands,
        },
        "environment": {
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
        },
        "commands": command_records,
        "summary": {
            "command_count": len(commands),
            "passed": len(commands),
            "failed": 0,
            "systems_observed": [system],
        },
        "scope": {
            "success_only": True,
            "network": "authorized loopback HTTP only",
            "repository": "disposable local Git fixture only",
            "secrets": (
                "environment values and private project data are not requested"
            ),
            "claim": "Observed evidence only.",
        },
    }
    document["evidence_sha256"] = sha256_value(document)
    return document


def write_document(path: Path, document: dict) -> Path:
    path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


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
    assert getpass.getuser() not in encoded
    if platform.node():
        assert platform.node() not in encoded
    assert "<fixture-root>" in encoded
    assert "<home>" in encoded
    assert "<hostname>" in encoded
    assert "http://127.0.0.1:<ephemeral-port>/ok" in encoded


def test_merge_accepts_three_declared_systems(tmp_path):
    files = [
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

    renamed_directory = tmp_path / "renamed"
    renamed_directory.mkdir()
    renamed_files = [
        write_document(
            renamed_directory / f"record-{index}.json",
            json.loads(path.read_text(encoding="utf-8")),
        )
        for index, path in enumerate(reversed(files), start=1)
    ]

    summary = merge(files)
    summary_reversed = merge(list(reversed(files)))
    summary_renamed = merge(renamed_files)

    assert summary == summary_reversed == summary_renamed
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
    assert summary["summary"]["environment_count"] == 3
    assert summary["summary"]["system_counts"] == {
        "Darwin": 1,
        "Linux": 1,
        "Windows": 1,
    }
    assert summary["summary"]["command_count"] == 15
    assert summary["summary"]["command_environment_runs"] == 45
    assert summary["summary"]["failed_command_runs"] == 0
    assert summary["requirements"]["declared_systems_observed"] is True
    assert all(
        command["declared_systems_observed"] is True
        for command in summary["commands"].values()
    )
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
