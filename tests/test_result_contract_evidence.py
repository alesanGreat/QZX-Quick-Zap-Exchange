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


def test_composite_action_runner_generates_receipt_output_and_summary(tmp_path):
    caller_workspace = tmp_path / "caller"
    caller_workspace.mkdir()
    for name in ("mcp-success.json", "mcp-failure.json", "mcp-tool-definition.json"):
        (caller_workspace / name).write_bytes((FIXTURE_ROOT / name).read_bytes())

    report_path = caller_workspace / "qzx-receipt.json"
    output_path = tmp_path / "github-output.txt"
    summary_path = tmp_path / "github-summary.md"
    environment = os.environ.copy()
    environment.update(
        {
            "INPUT_PROFILE": "mcp-2026-07-28",
            "INPUT_SUCCESS": "mcp-success.json",
            "INPUT_FAILURE": "mcp-failure.json",
            "INPUT_TOOL_DEFINITION": "mcp-tool-definition.json",
            "INPUT_REPORT": "qzx-receipt.json",
            "GITHUB_WORKSPACE": str(caller_workspace),
            "GITHUB_OUTPUT": str(output_path),
            "GITHUB_STEP_SUMMARY": str(summary_path),
        }
    )

    process = subprocess.run(
        [sys.executable, str(ACTION_RUNNER)],
        cwd=REPOSITORY_ROOT,
        env=environment,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert process.returncode == 0, process.stderr
    receipt = json.loads(report_path.read_text(encoding="utf-8"))
    assert receipt["success"] is True
    contract_schema_sha256 = receipt["details"]["validation_materials"][
        "contract_schema"
    ]["sha256"]
    action_output = output_path.read_text(encoding="utf-8")
    assert "report=qzx-receipt.json" in action_output
    assert "conformant=true" in action_output
    assert "profile=mcp-2026-07-28" in action_output
    assert f"receipt_schema={validator.CONFORMANCE_RECEIPT_SCHEMA_URL}" in action_output
    assert f"contract_schema_sha256={contract_schema_sha256}" in action_output
    assert "output_schema_mode=canonical_ref" in action_output
    assert "failure_kind=none" in action_output
    summary = summary_path.read_text(encoding="utf-8")
    assert "Status: **PASS**" in summary
    assert "Failure kind: `none`" in summary
    assert "mcp-2026-07-28" in summary
    assert "Output schema mode: `canonical_ref`" in summary
    assert validator.CONFORMANCE_RECEIPT_SCHEMA_URL in summary
    assert contract_schema_sha256 in summary
    assert "QZX Result Contract v1" in summary
    assert "Alejandro Sánchez" in summary


def test_composite_action_rejects_workspace_escape_and_output_injection(tmp_path):
    caller_workspace = tmp_path / "caller"
    caller_workspace.mkdir()
    (caller_workspace / "failure.json").write_bytes(
        (FIXTURE_ROOT / "valid-failure.json").read_bytes()
    )
    (caller_workspace / "success.json").write_bytes(
        (FIXTURE_ROOT / "valid-success.json").read_bytes()
    )
    outside_success = tmp_path / "outside-success.json"
    outside_success.write_bytes((FIXTURE_ROOT / "valid-success.json").read_bytes())

    environment = os.environ.copy()
    environment.update(
        {
            "INPUT_PROFILE": "core",
            "INPUT_SUCCESS": str(outside_success),
            "INPUT_FAILURE": "failure.json",
            "INPUT_TOOL_DEFINITION": "",
            "INPUT_REPORT": "qzx-receipt.json",
            "GITHUB_WORKSPACE": str(caller_workspace),
            "GITHUB_OUTPUT": str(tmp_path / "github-output.txt"),
            "GITHUB_STEP_SUMMARY": str(tmp_path / "github-summary.md"),
        }
    )
    escape_process = subprocess.run(
        [sys.executable, str(ACTION_RUNNER)],
        cwd=REPOSITORY_ROOT,
        env=environment,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert escape_process.returncode == 2
    assert "must stay inside GITHUB_WORKSPACE" in escape_process.stderr
    escape_output = (tmp_path / "github-output.txt").read_text(encoding="utf-8")
    assert "report=unavailable" in escape_output
    assert "conformant=false" in escape_output
    assert "profile=core" in escape_output
    assert "failure_kind=operational" in escape_output
    escape_summary = (tmp_path / "github-summary.md").read_text(encoding="utf-8")
    assert "Status: **FAIL**" in escape_summary
    assert "Failure kind: `operational`" in escape_summary
    assert "must stay inside GITHUB_WORKSPACE" in escape_summary

    environment["INPUT_SUCCESS"] = "success.json"
    environment["INPUT_REPORT"] = "receipt.json\ninjected=true"
    environment["GITHUB_OUTPUT"] = str(tmp_path / "injection-output.txt")
    environment["GITHUB_STEP_SUMMARY"] = str(tmp_path / "injection-summary.md")
    injection_process = subprocess.run(
        [sys.executable, str(ACTION_RUNNER)],
        cwd=REPOSITORY_ROOT,
        env=environment,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert injection_process.returncode == 2
    assert "must not contain line breaks" in injection_process.stderr
    injection_output = (tmp_path / "injection-output.txt").read_text(
        encoding="utf-8"
    )
    assert "report=unavailable" in injection_output
    assert "failure_kind=operational" in injection_output
    assert "injected=true" not in injection_output


def test_composite_action_distinguishes_conformance_failure(tmp_path):
    caller_workspace = tmp_path / "caller"
    caller_workspace.mkdir()
    for name in ("valid-success.json", "valid-failure.json"):
        (caller_workspace / name).write_bytes((FIXTURE_ROOT / name).read_bytes())

    output_path = tmp_path / "github-output.txt"
    summary_path = tmp_path / "github-summary.md"
    environment = os.environ.copy()
    environment.update(
        {
            "INPUT_PROFILE": "core",
            "INPUT_SUCCESS": "valid-failure.json",
            "INPUT_FAILURE": "valid-failure.json",
            "INPUT_TOOL_DEFINITION": "",
            "INPUT_REPORT": "qzx-receipt.json",
            "GITHUB_WORKSPACE": str(caller_workspace),
            "GITHUB_OUTPUT": str(output_path),
            "GITHUB_STEP_SUMMARY": str(summary_path),
        }
    )

    process = subprocess.run(
        [sys.executable, str(ACTION_RUNNER)],
        cwd=REPOSITORY_ROOT,
        env=environment,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )

    assert process.returncode == 1
    action_output = output_path.read_text(encoding="utf-8")
    assert "report=qzx-receipt.json" in action_output
    assert "conformant=false" in action_output
    assert "failure_kind=conformance" in action_output
    summary = summary_path.read_text(encoding="utf-8")
    assert "Status: **FAIL**" in summary
    assert "Failure kind: `conformance`" in summary


def test_composite_action_timeout_is_an_operational_failure(tmp_path, monkeypatch, capsys):
    caller_workspace = tmp_path / "caller"
    caller_workspace.mkdir()
    for name in ("valid-success.json", "valid-failure.json"):
        (caller_workspace / name).write_bytes((FIXTURE_ROOT / name).read_bytes())

    output_path = tmp_path / "github-output.txt"
    summary_path = tmp_path / "github-summary.md"
    environment = {
        "INPUT_PROFILE": "core",
        "INPUT_SUCCESS": "valid-success.json",
        "INPUT_FAILURE": "valid-failure.json",
        "INPUT_TOOL_DEFINITION": "",
        "INPUT_REPORT": "qzx-receipt.json",
        "GITHUB_WORKSPACE": str(caller_workspace),
        "GITHUB_OUTPUT": str(output_path),
        "GITHUB_STEP_SUMMARY": str(summary_path),
    }
    for name, value in environment.items():
        monkeypatch.setenv(name, value)

    def time_out(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])

    assert action_runner.run_action(process_runner=time_out) == 2
    assert "120-second execution limit" in capsys.readouterr().err
    action_output = output_path.read_text(encoding="utf-8")
    assert "report=unavailable" in action_output
    assert "conformant=false" in action_output
    assert "failure_kind=operational" in action_output
    summary = summary_path.read_text(encoding="utf-8")
    assert "Failure kind: `operational`" in summary
    assert "120-second execution limit" in summary


def test_composite_action_rejects_unknown_profile_without_reflecting_it(tmp_path):
    output_path = tmp_path / "github-output.txt"
    summary_path = tmp_path / "github-summary.md"
    environment = os.environ.copy()
    environment.update(
        {
            "INPUT_PROFILE": "unknown-profile",
            "INPUT_SUCCESS": "success.json",
            "INPUT_FAILURE": "failure.json",
            "INPUT_TOOL_DEFINITION": "",
            "INPUT_REPORT": "qzx-receipt.json",
            "GITHUB_WORKSPACE": str(tmp_path),
            "GITHUB_OUTPUT": str(output_path),
            "GITHUB_STEP_SUMMARY": str(summary_path),
        }
    )

    process = subprocess.run(
        [sys.executable, str(ACTION_RUNNER)],
        cwd=REPOSITORY_ROOT,
        env=environment,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )

    assert process.returncode == 2
    assert "INPUT_PROFILE must be one of" in process.stderr
    action_output = output_path.read_text(encoding="utf-8")
    assert "profile=unavailable" in action_output
    assert "failure_kind=operational" in action_output
    assert "unknown-profile" not in action_output


def test_composite_action_does_not_claim_an_unwritten_receipt(tmp_path):
    caller_workspace = tmp_path / "caller"
    caller_workspace.mkdir()
    for name in ("valid-success.json", "valid-failure.json"):
        (caller_workspace / name).write_bytes((FIXTURE_ROOT / name).read_bytes())
    (caller_workspace / "receipt-target").mkdir()

    output_path = tmp_path / "github-output.txt"
    summary_path = tmp_path / "github-summary.md"
    environment = os.environ.copy()
    environment.update(
        {
            "INPUT_PROFILE": "core",
            "INPUT_SUCCESS": "valid-success.json",
            "INPUT_FAILURE": "valid-failure.json",
            "INPUT_TOOL_DEFINITION": "",
            "INPUT_REPORT": "receipt-target",
            "GITHUB_WORKSPACE": str(caller_workspace),
            "GITHUB_OUTPUT": str(output_path),
            "GITHUB_STEP_SUMMARY": str(summary_path),
        }
    )

    process = subprocess.run(
        [sys.executable, str(ACTION_RUNNER)],
        cwd=REPOSITORY_ROOT,
        env=environment,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )

    assert process.returncode == 1
    action_output = output_path.read_text(encoding="utf-8")
    assert "report=unavailable" in action_output
    assert "conformant=false" in action_output
    assert "failure_kind=operational" in action_output
    assert f"receipt_schema={validator.CONFORMANCE_RECEIPT_SCHEMA_URL}" in action_output
    summary = summary_path.read_text(encoding="utf-8")
    assert "Receipt: `unavailable`" in summary
    assert "Failure kind: `operational`" in summary


def test_composite_action_metadata_pins_python_setup_and_exposes_inputs():
    assert action_runner.SUPPORTED_PROFILES == {
        validator.PROFILE_CORE,
        *validator.MCP_PROFILES,
    }
    for metadata_path in (ACTION_METADATA, NESTED_ACTION_METADATA):
        metadata = metadata_path.read_text(encoding="utf-8")
        assert "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97" in metadata
        assert 'python-version: "3.13"' in metadata
        assert "INPUT_SUCCESS: ${{ inputs.success }}" in metadata
        assert "INPUT_FAILURE: ${{ inputs.failure }}" in metadata
        assert "INPUT_TOOL_DEFINITION: ${{ inputs.tool-definition }}" in metadata
        assert "value: ${{ steps.validate.outputs.conformant }}" in metadata
        assert "value: ${{ steps.validate.outputs.profile }}" in metadata
        assert "value: ${{ steps.validate.outputs.receipt_schema }}" in metadata
        assert "value: ${{ steps.validate.outputs.contract_schema_sha256 }}" in metadata
        assert "value: ${{ steps.validate.outputs.failure_kind }}" in metadata


def test_composite_action_readme_documents_all_scalar_outputs():
    readme = ACTION_README.read_text(encoding="utf-8")
    for output_name in (
        "report",
        "conformant",
        "profile",
        "receipt_schema",
        "contract_schema_sha256",
        "output_schema_mode",
        "failure_kind",
    ):
        assert f"| `{output_name}` |" in readme


def test_public_adoption_examples_are_reproducibly_pinned():
    action_readme = ACTION_README.read_text(encoding="utf-8")
    quickstart = QUICKSTART.read_text(encoding="utf-8")
    adoption_guide = ADOPTION_GUIDE.read_text(encoding="utf-8")

    for document in (action_readme, quickstart):
        assert f"actions/checkout@{CHECKOUT_V7_SHA}" in document
        assert (
            f"alesangreat/QZX-Quick-Zap-Exchange@{QZX_CONFORMANCE_ACTION_SHA}"
            in document
        )
        assert "alesangreat/QZX-Quick-Zap-Exchange@main" not in document
        assert (
            "QZX-Quick-Zap-Exchange/.github/actions/result-contract-conformance@"
            not in document
        )
        assert "actions/checkout@v7" not in document

    assert "`canonical_inline`" in quickstart
    assert "contract_schema_sha256" in quickstart
    assert "vendored canonical object" in adoption_guide
    assert "validation_materials" in adoption_guide


def test_nonconformance_receipt_is_preserved_by_ci_and_documented_for_callers():
    """Keep failed conformance reviewable instead of losing the receipt with the job."""

    workflow = (REPOSITORY_ROOT / ".github" / "workflows" / "test.yml").read_text(
        encoding="utf-8"
    )
    assert "Validate intentionally nonconforming evidence" in workflow
    assert "continue-on-error: true" in workflow
    assert "qzx-nonconforming-receipt.json" in workflow
    assert "steps.qzx-nonconforming.outputs.failure_kind == 'conformance'" in workflow
    assert (
        "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"
        in workflow
    )
    assert "Verify nonconformance Action failure and receipt" in workflow

    quickstart = QUICKSTART.read_text(encoding="utf-8")
    assert "Preserve the receipt even when conformance fails" in quickstart
    assert "continue-on-error: true" in quickstart
    assert "steps.qzx-conformance.outputs.failure_kind == 'none'" in quickstart
    assert "steps.qzx-conformance.outputs.failure_kind == 'conformance'" in quickstart
    assert "steps.qzx-conformance.outcome == 'failure'" in quickstart
    assert "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a" in quickstart


def test_public_workflow_examples_avoid_duplicate_ci_and_moving_runner_defaults():
    """Keep copyable workflows deterministic, read-only, and free of duplicate PR CI."""

    quickstart = QUICKSTART.read_text(encoding="utf-8")
    expected_triggers = (
        "on:\n"
        "  push:\n"
        "    branches:\n"
        "      - main\n"
        "  pull_request:\n"
        "  workflow_dispatch:\n"
    )
    assert expected_triggers in quickstart
    assert "on: [push, pull_request]" not in quickstart
    assert "permissions:\n  contents: read\n" in quickstart
    assert "runs-on: ubuntu-24.04" in quickstart
    assert "runs-on: ubuntu-latest" not in quickstart
    assert (
        f"actions/checkout@{CHECKOUT_V7_SHA} # v7\n"
        "        with:\n"
        "          persist-credentials: false"
        in quickstart
    )

    action_readme = ACTION_README.read_text(encoding="utf-8")
    assert action_readme.count("persist-credentials: false") >= 2
