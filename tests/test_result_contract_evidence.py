#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Regression tests for the external QZX Result Contract conformance kit."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPOSITORY_ROOT / "scripts" / "validate_result_contract_evidence.py"
ACTION_ROOT = REPOSITORY_ROOT / ".github" / "actions" / "result-contract-conformance"
ACTION_RUNNER = ACTION_ROOT / "run.py"
ACTION_METADATA = REPOSITORY_ROOT / "action.yml"
NESTED_ACTION_METADATA = ACTION_ROOT / "action.yml"
ACTION_README = ACTION_ROOT / "README.md"
QUICKSTART = REPOSITORY_ROOT / "docs" / "result-contract-quickstart.md"
ADOPTION_GUIDE = REPOSITORY_ROOT / "docs" / "result-contract-adoption.md"
FIXTURE_ROOT = REPOSITORY_ROOT / "examples" / "result_contract"
CHECKOUT_V7_SHA = "3d3c42e5aac5ba805825da76410c181273ba90b1"
QZX_CONFORMANCE_ACTION_SHA = "6a912448c7b2aa41c2a48923c355c422c02cd7a2"

spec = importlib.util.spec_from_file_location("qzx_evidence_validator", SCRIPT_PATH)
validator = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(validator)

action_spec = importlib.util.spec_from_file_location("qzx_action_runner", ACTION_RUNNER)
action_runner = importlib.util.module_from_spec(action_spec)
assert action_spec.loader is not None
action_spec.loader.exec_module(action_runner)


def test_core_success_failure_pair_produces_deterministic_receipt():
    report = validator.validate_evidence(
        profile=validator.PROFILE_CORE,
        success_path=str(FIXTURE_ROOT / "valid-success.json"),
        failure_path=str(FIXTURE_ROOT / "valid-failure.json"),
    )

    assert report["success"] is True
    assert report["receipt_schema"] == validator.CONFORMANCE_RECEIPT_SCHEMA_URL
    assert report["details"]["contract_version"] == "v1"
    assert report["details"]["profile"] == "core"
    assert report["details"]["mcp_specification"] is None
    assert [case["actual_success"] for case in report["details"]["cases"]] == [
        True,
        False,
    ]
    assert all(case["conformant"] for case in report["details"]["cases"])
    assert all(len(case["sha256"]) == 64 for case in report["details"]["cases"])

    materials = report["details"]["validation_materials"]
    assert set(materials) == set(validator.VALIDATION_MATERIAL_PATHS)
    for name, repository_path in validator.VALIDATION_MATERIAL_PATHS.items():
        material = materials[name]
        assert material["repository_path"] == repository_path
        expected_digest = hashlib.sha256(
            (REPOSITORY_ROOT / repository_path).read_bytes()
        ).hexdigest()
        assert material["sha256"] == expected_digest


def test_mcp_success_failure_pair_checks_tool_definition():
    report = validator.validate_evidence(
        profile=validator.PROFILE_MCP,
        success_path=str(FIXTURE_ROOT / "mcp-success.json"),
        failure_path=str(FIXTURE_ROOT / "mcp-failure.json"),
        tool_definition_path=str(FIXTURE_ROOT / "mcp-tool-definition.json"),
    )

    assert report["success"] is True
    assert report["details"]["mcp_specification"] == "2026-07-28"
    assert len(report["details"]["tool_definition"]["sha256"]) == 64
    assert all(
        case["profile_facts"]["output_schema_checked"] is True
        for case in report["details"]["cases"]
    )
    assert all(
        case["profile_facts"]["output_schema_mode"] == "canonical_ref"
        for case in report["details"]["cases"]
    )


def test_structural_mcp_fixture_is_visible_in_2025_receipt():
    report = validator.validate_evidence(
        profile="mcp-2025-11-25",
        success_path=str(FIXTURE_ROOT / "mcp-2025-success.json"),
        failure_path=str(FIXTURE_ROOT / "mcp-2025-failure.json"),
        tool_definition_path=str(
            FIXTURE_ROOT / "mcp-structural-tool-definition.json"
        ),
    )

    assert report["success"] is True
    assert report["details"]["mcp_specification"] == "2025-11-25"
    assert all(
        case["profile_facts"]["output_schema_mode"] == "structural_core"
        for case in report["details"]["cases"]
    )
    assert all(case["warnings"] for case in report["details"]["cases"])


def test_legacy_mcp_profiles_accept_checked_in_2025_fixtures():
    for profile, specification in (
        ("mcp-2025-06-18", "2025-06-18"),
        ("mcp-2025-11-25", "2025-11-25"),
    ):
        report = validator.validate_evidence(
            profile=profile,
            success_path=str(FIXTURE_ROOT / "mcp-2025-success.json"),
            failure_path=str(FIXTURE_ROOT / "mcp-2025-failure.json"),
            tool_definition_path=str(FIXTURE_ROOT / "mcp-tool-definition.json"),
        )
        assert report["success"] is True
        assert report["details"]["profile"] == profile
        assert report["details"]["mcp_specification"] == specification
        assert all(case["conformant"] for case in report["details"]["cases"])


def test_evidence_pair_rejects_wrong_semantic_roles_and_missing_mcp_definition():
    reversed_report = validator.validate_evidence(
        profile=validator.PROFILE_CORE,
        success_path=str(FIXTURE_ROOT / "valid-failure.json"),
        failure_path=str(FIXTURE_ROOT / "valid-success.json"),
    )
    assert reversed_report["success"] is False
    assert any(
        "success evidence must represent success=true." in violation
        for violation in reversed_report["details"]["cases"][0]["violations"]
    )
    assert any(
        "failure evidence must represent success=false." in violation
        for violation in reversed_report["details"]["cases"][1]["violations"]
    )

    mcp_without_definition = validator.validate_evidence(
        profile=validator.PROFILE_MCP,
        success_path=str(FIXTURE_ROOT / "mcp-success.json"),
        failure_path=str(FIXTURE_ROOT / "mcp-failure.json"),
    )
    assert mcp_without_definition["success"] is False
    assert mcp_without_definition["error_code"] == "conformance_failed"
    assert mcp_without_definition["details"]["violations"] == [
        "The MCP profile requires --tool-definition so outputSchema is reviewable."
    ]


def test_cli_writes_same_receipt_it_prints(tmp_path):
    report_path = tmp_path / "receipt.json"
    process = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--profile",
            "mcp-2026-07-28",
            "--success",
            str(FIXTURE_ROOT / "mcp-success.json"),
            "--failure",
            str(FIXTURE_ROOT / "mcp-failure.json"),
            "--tool-definition",
            str(FIXTURE_ROOT / "mcp-tool-definition.json"),
            "--report",
            str(report_path),
            "--json",
        ],
        cwd=REPOSITORY_ROOT,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout) == json.loads(report_path.read_text(encoding="utf-8"))


def test_cli_write_failure_remains_a_valid_result_contract(tmp_path):
    report_directory = tmp_path / "receipt-directory"
    report_directory.mkdir()
    process = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--profile",
            "core",
            "--success",
            str(FIXTURE_ROOT / "valid-success.json"),
            "--failure",
            str(FIXTURE_ROOT / "valid-failure.json"),
            "--report",
            str(report_directory),
            "--json",
        ],
        cwd=REPOSITORY_ROOT,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert process.returncode == 1
    report = json.loads(process.stdout)
    assert report["success"] is False
    assert report["error_code"] == "receipt_write_failed"
    assert report["receipt_schema"] == validator.CONFORMANCE_RECEIPT_SCHEMA_URL
    assert validator.result_contract_violations(report) == []


def test_cli_refuses_to_overwrite_an_evidence_input_with_its_receipt(tmp_path):
    success_path = tmp_path / "success.json"
    failure_path = tmp_path / "failure.json"
    success_path.write_bytes((FIXTURE_ROOT / "valid-success.json").read_bytes())
    failure_path.write_bytes((FIXTURE_ROOT / "valid-failure.json").read_bytes())
    original_success = success_path.read_bytes()

    process = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--profile",
            "core",
            "--success",
            str(success_path),
            "--failure",
            str(failure_path),
            "--report",
            str(success_path),
            "--json",
        ],
        cwd=REPOSITORY_ROOT,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )

    assert process.returncode == 1
    assert success_path.read_bytes() == original_success
    report = json.loads(process.stdout)
    assert report["success"] is False
    assert report["error_code"] == "receipt_path_conflict"
    assert report["details"]["violations"] == [
        "The report path must differ from the success evidence path; "
        "no receipt was written."
    ]
    assert validator.result_contract_violations(report) == []


def test_conflict_detection_handles_lexical_aliases_and_symlink_loops(tmp_path):
    evidence = tmp_path / "evidence.json"
    evidence.write_text("{}\n", encoding="utf-8")
    lexical_alias = tmp_path / "nested" / ".." / "evidence.json"

    assert (
        validator._conflicting_evidence_role(
            str(lexical_alias),
            success_path=str(evidence),
            failure_path=str(tmp_path / "failure.json"),
            tool_definition_path=None,
        )
        == "success"
    )

    loop = tmp_path / "loop"
    loop.symlink_to(loop.name)
    try:
        assert (
            validator._conflicting_evidence_role(
                str(loop),
                success_path=str(evidence),
                failure_path=str(tmp_path / "failure.json"),
                tool_definition_path=None,
            )
            is None
        )
    finally:
        loop.unlink()


def test_atomic_receipt_write_failure_preserves_existing_file(tmp_path):
    report_path = tmp_path / "receipt.json"
    original = b"previous receipt\n"
    report_path.write_bytes(original)

    def refuse_replace(_source, _destination):
        raise OSError("synthetic replace failure")

    with pytest.raises(OSError, match="synthetic replace failure"):
        validator._write_text_atomic(
            report_path,
            "new receipt\n",
            replace_file=refuse_replace,
        )

    assert report_path.read_bytes() == original
    assert list(tmp_path.glob(".receipt.json.*.tmp")) == []


def test_cli_refuses_to_overwrite_a_hard_link_to_evidence(tmp_path):
    success_path = tmp_path / "success.json"
    failure_path = tmp_path / "failure.json"
    report_path = tmp_path / "receipt.json"
    success_path.write_bytes((FIXTURE_ROOT / "valid-success.json").read_bytes())
    failure_path.write_bytes((FIXTURE_ROOT / "valid-failure.json").read_bytes())
    os.link(success_path, report_path)
    original_success = success_path.read_bytes()

    process = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--profile",
            "core",
            "--success",
            str(success_path),
            "--failure",
            str(failure_path),
            "--report",
            str(report_path),
            "--json",
        ],
        cwd=REPOSITORY_ROOT,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )

    assert process.returncode == 1
    assert success_path.read_bytes() == original_success
    assert report_path.read_bytes() == original_success
    report = json.loads(process.stdout)
    assert report["success"] is False
    assert report["error_code"] == "receipt_path_conflict"
    assert report["details"]["violations"] == [
        "The report path must differ from the success evidence path; "
        "no receipt was written."
    ]
    assert validator.result_contract_violations(report) == []


def test_evidence_validator_rejects_ambiguous_json_and_preserves_its_digest(
    tmp_path,
):
    ambiguous = tmp_path / "ambiguous.json"
    ambiguous.write_text(
        '{"success":true,"success":false,"message":"Ambiguous."}',
        encoding="utf-8",
    )

    document, digest, errors = validator._read_json(str(ambiguous))

    assert document is None
    assert digest == hashlib.sha256(ambiguous.read_bytes()).hexdigest()
    assert len(errors) == 1
    assert "Duplicate JSON object member name" in errors[0]
