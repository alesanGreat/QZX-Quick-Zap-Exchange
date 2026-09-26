#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Regression tests for the QZX Result Contract composite Action and adoption docs."""

from __future__ import annotations

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


def _copy_fixtures(workspace, names):
    for name in names:
        (workspace / name).write_bytes((FIXTURE_ROOT / name).read_bytes())


def _action_environment(
    workspace,
    output_path,
    summary_path,
    *,
    profile="core",
    success="valid-success.json",
    failure="valid-failure.json",
    tool_definition="",
    report="qzx-receipt.json",
):
    environment = os.environ.copy()
    environment.update(
        {
            "INPUT_PROFILE": profile,
            "INPUT_SUCCESS": success,
            "INPUT_FAILURE": failure,
            "INPUT_TOOL_DEFINITION": tool_definition,
            "INPUT_REPORT": report,
            "GITHUB_WORKSPACE": str(workspace),
            "GITHUB_OUTPUT": str(output_path),
            "GITHUB_STEP_SUMMARY": str(summary_path),
        }
    )
    return environment


def _run_action(environment):
    return subprocess.run(
        [sys.executable, str(ACTION_RUNNER)],
        cwd=REPOSITORY_ROOT,
        env=environment,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )


def _assert_successful_action_artifacts(receipt, output_path, summary_path):
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


def _assert_workspace_escape_failure(process, root):
    assert process.returncode == 2
    assert "must stay inside GITHUB_WORKSPACE" in process.stderr
    output = (root / "github-output.txt").read_text(encoding="utf-8")
    assert "report=unavailable" in output
    assert "conformant=false" in output
    assert "profile=core" in output
    assert "failure_kind=operational" in output
    summary = (root / "github-summary.md").read_text(encoding="utf-8")
    assert "Status: **FAIL**" in summary
    assert "Failure kind: `operational`" in summary
    assert "must stay inside GITHUB_WORKSPACE" in summary


def _assert_output_injection_failure(process, root):
    assert process.returncode == 2
    assert "must not contain line breaks" in process.stderr
    output = (root / "injection-output.txt").read_text(encoding="utf-8")
    assert "report=unavailable" in output
    assert "failure_kind=operational" in output
    assert "injected=true" not in output


def test_composite_action_runner_generates_receipt_output_and_summary(tmp_path):
    caller_workspace = tmp_path / "caller"
    caller_workspace.mkdir()
    _copy_fixtures(
        caller_workspace,
        ("mcp-success.json", "mcp-failure.json", "mcp-tool-definition.json"),
    )
    report_path = caller_workspace / "qzx-receipt.json"
    output_path = tmp_path / "github-output.txt"
    summary_path = tmp_path / "github-summary.md"
    environment = _action_environment(
        caller_workspace,
        output_path,
        summary_path,
        profile="mcp-2026-07-28",
        success="mcp-success.json",
        failure="mcp-failure.json",
        tool_definition="mcp-tool-definition.json",
    )

    process = _run_action(environment)

    assert process.returncode == 0, process.stderr
    receipt = json.loads(report_path.read_text(encoding="utf-8"))
    assert receipt["success"] is True
    _assert_successful_action_artifacts(receipt, output_path, summary_path)


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
    environment = _action_environment(
        caller_workspace,
        tmp_path / "github-output.txt",
        tmp_path / "github-summary.md",
        success=str(outside_success),
        failure="failure.json",
    )

    escape_process = _run_action(environment)
    _assert_workspace_escape_failure(escape_process, tmp_path)

    environment["INPUT_SUCCESS"] = "success.json"
    environment["INPUT_REPORT"] = "receipt.json\ninjected=true"
    environment["GITHUB_OUTPUT"] = str(tmp_path / "injection-output.txt")
    environment["GITHUB_STEP_SUMMARY"] = str(tmp_path / "injection-summary.md")
    injection_process = _run_action(environment)
    _assert_output_injection_failure(injection_process, tmp_path)


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
