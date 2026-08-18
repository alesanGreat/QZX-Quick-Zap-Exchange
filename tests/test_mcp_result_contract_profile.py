#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Regression tests for the QZX Result Contract v1 MCP profile validator."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPOSITORY_ROOT / "scripts" / "validate_mcp_result_contract.py"
FIXTURE_ROOT = REPOSITORY_ROOT / "examples" / "result_contract"
TOOL_DEFINITION = FIXTURE_ROOT / "mcp-tool-definition.json"


spec = importlib.util.spec_from_file_location("qzx_mcp_profile_validator", SCRIPT_PATH)
validator = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(validator)


def load_fixture(name):
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))


def without_result_type(name):
    document = load_fixture(name)
    document["result"].pop("resultType", None)
    return document


def test_success_and_failure_fixtures_conform_with_output_schema():
    tool_definition = load_fixture("mcp-tool-definition.json")
    for fixture_name in ("mcp-success.json", "mcp-failure.json"):
        violations, warnings, details = validator.validate_mcp_profile(
            load_fixture(fixture_name),
            tool_definition,
        )
        assert violations == []
        assert warnings == []
        assert details["output_schema_checked"] is True
        assert details["output_schema_mode"] == validator.OUTPUT_SCHEMA_CANONICAL_REF
        assert details["backcompat_text_matches"] is True


def test_allof_composition_preserves_canonical_schema_claim():
    tool_definition = {
        "name": "example",
        "outputSchema": {
            "allOf": [
                {"$ref": validator.RESULT_CONTRACT_SCHEMA_URL},
                {
                    "type": "object",
                    "properties": {"data": {"type": "object"}},
                },
            ]
        },
    }
    violations, warnings, details = validator.validate_mcp_profile(
        load_fixture("mcp-success.json"),
        tool_definition,
    )
    assert violations == []
    assert warnings == []
    assert details["output_schema_mode"] == validator.OUTPUT_SCHEMA_CANONICAL_ALLOF


def test_structural_output_schema_is_portable_but_reported_as_weaker_evidence():
    violations, warnings, details = validator.validate_mcp_profile(
        load_fixture("mcp-success.json"),
        load_fixture("mcp-structural-tool-definition.json"),
    )
    assert violations == []
    assert warnings == [
        "outputSchema exposes the QZX core structurally but does not embed the "
        "canonical QZX schema. The submitted runtime evidence is validated "
        "against the full Result Contract, but outputSchema alone does not "
        "guarantee every QZX invariant."
    ]
    assert details["output_schema_mode"] == validator.OUTPUT_SCHEMA_STRUCTURAL_CORE


def test_structural_output_schema_rejects_weak_or_bypass_shapes():
    weak = load_fixture("mcp-structural-tool-definition.json")
    weak["outputSchema"]["properties"]["message"]["pattern"] = "\\S?"
    weak["outputSchema"]["properties"]["success"]["type"] = ["boolean", "null"]
    violations, _, details = validator.validate_mcp_profile(
        load_fixture("mcp-success.json"),
        weak,
    )
    assert any("non-empty, non-whitespace" in item for item in violations)
    assert any("exactly boolean" in item for item in violations)
    assert details["output_schema_mode"] is None

    bypass = {
        "name": "example",
        "outputSchema": {
            "anyOf": [
                {"$ref": validator.RESULT_CONTRACT_SCHEMA_URL},
                {"type": "object"},
            ]
        },
    }
    violations, _, details = validator.validate_mcp_profile(
        load_fixture("mcp-success.json"),
        bypass,
    )
    assert violations
    assert details["output_schema_mode"] is None


def test_legacy_structured_output_fixtures_do_not_require_result_type():
    tool_definition = load_fixture("mcp-tool-definition.json")
    for specification_version in ("2025-06-18", "2025-11-25"):
        for fixture_name in ("mcp-2025-success.json", "mcp-2025-failure.json"):
            document = load_fixture(fixture_name)
            assert "resultType" not in document["result"]
            violations, warnings, details = validator.validate_mcp_profile(
                document,
                tool_definition,
                specification_version,
            )
            assert violations == []
            assert warnings == []
            assert details["mcp_specification"] == specification_version
            assert details["mcp_tools_spec"].endswith(
                f"/{specification_version}/server/tools"
            )


def test_2026_07_28_profile_requires_complete_result_type():
    violations, warnings, details = validator.validate_mcp_profile(
        without_result_type("mcp-success.json"),
        load_fixture("mcp-tool-definition.json"),
        "2026-07-28",
    )
    assert violations == [
        "The MCP 2026-07-28 profile applies only to resultType 'complete'."
    ]
    assert warnings == []
    assert details["mcp_specification"] == "2026-07-28"


def test_is_error_must_match_qzx_success():
    violations, warnings, details = validator.validate_mcp_profile(
        load_fixture("mcp-invalid-is-error.json")
    )
    assert (
        "Effective MCP isError must equal !structuredContent.success for a "
        "completed QZX MCP profile result. MCP treats omitted isError as false."
    ) in violations
    assert warnings == []
    assert details["backcompat_text_matches"] is True


def test_success_may_omit_is_error_because_mcp_defaults_it_to_false():
    document = load_fixture("mcp-2025-success.json")
    document["result"].pop("isError")
    violations, warnings, details = validator.validate_mcp_profile(
        document,
        load_fixture("mcp-structural-tool-definition.json"),
        "2025-11-25",
    )
    assert violations == []
    assert warnings == [
        "outputSchema exposes the QZX core structurally but does not embed the "
        "canonical QZX schema. The submitted runtime evidence is validated "
        "against the full Result Contract, but outputSchema alone does not "
        "guarantee every QZX invariant."
    ]
    assert details["mcp_is_error_explicit"] is False
    assert details["mcp_is_error_effective"] is False


def test_failure_must_set_is_error_true_even_though_the_field_is_optional():
    document = load_fixture("mcp-2025-failure.json")
    document["result"].pop("isError")
    violations, warnings, details = validator.validate_mcp_profile(
        document,
        load_fixture("mcp-structural-tool-definition.json"),
        "2025-11-25",
    )
    assert (
        "Effective MCP isError must equal !structuredContent.success for a "
        "completed QZX MCP profile result. MCP treats omitted isError as false."
    ) in violations
    assert details["mcp_is_error_explicit"] is False
    assert details["mcp_is_error_effective"] is False


def test_protocol_error_is_not_a_completed_qzx_result():
    violations, warnings, details = validator.validate_mcp_profile(
        load_fixture("mcp-protocol-error.json")
    )
    assert violations == [
        "MCP protocol errors are not completed QZX Result Contract results."
    ]
    assert warnings == []
    assert details["backcompat_text_matches"] is False


def test_jsonrpc_response_cannot_mix_result_and_error():
    document = load_fixture("mcp-success.json")
    document["error"] = {"code": -32603, "message": "Contradictory error."}

    violations, warnings, details = validator.validate_mcp_profile(document)

    assert violations == [
        "A JSON-RPC response must contain exactly one of result or error."
    ]
    assert warnings == []
    assert details["backcompat_text_matches"] is False


def test_jsonrpc_result_response_requires_an_mcp_request_id():
    for invalid_id in (None, True, 1.5):
        document = load_fixture("mcp-success.json")
        document["id"] = invalid_id

        violations, _, _ = validator.validate_mcp_profile(document)

        assert (
            "An MCP JSON-RPC result response must include a string or integer id."
            in violations
        )

    document = load_fixture("mcp-success.json")
    del document["id"]
    violations, _, _ = validator.validate_mcp_profile(document)
    assert (
        "An MCP JSON-RPC result response must include a string or integer id."
        in violations
    )


def test_backwards_compatibility_text_is_a_warning_not_core_failure():
    document = {
        "resultType": "complete",
        "content": [{"type": "text", "text": "Operation completed."}],
        "structuredContent": {
            "success": True,
            "message": "Operation completed.",
        },
        "isError": False,
    }
    violations, warnings, details = validator.validate_mcp_profile(document)
    assert violations == []
    assert warnings == [
        "No TextContent block serializes the complete structuredContent object. "
        "MCP recommends this for backwards compatibility."
    ]
    assert details["backcompat_text_matches"] is False


def test_cli_json_report_accepts_full_jsonrpc_response():
    process = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            str(FIXTURE_ROOT / "mcp-success.json"),
            "--tool-definition",
            str(TOOL_DEFINITION),
            "--json",
        ],
        cwd=REPOSITORY_ROOT,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert process.returncode == 0, process.stderr
    report = json.loads(process.stdout)
    assert report["success"] is True
    assert report["details"]["mcp_specification"] == "2026-07-28"
    assert report["details"]["output_schema_checked"] is True
    assert report["details"]["violations"] == []


def test_mcp_cli_rejects_duplicate_jsonrpc_members(tmp_path):
    duplicate_response = tmp_path / "duplicate-response.json"
    duplicate_response.write_text(
        '{"jsonrpc":"2.0","id":1,"result":{},"result":{}}',
        encoding="utf-8",
    )

    process = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), str(duplicate_response), "--json"],
        cwd=REPOSITORY_ROOT,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )

    assert process.returncode == 1, process.stderr
    report = json.loads(process.stdout)
    assert report["error_code"] == "invalid_json_input"
    assert "Duplicate JSON object member name" in report["error"]


def test_cli_accepts_checked_in_2025_11_25_fixture_without_result_type():
    process = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            str(FIXTURE_ROOT / "mcp-2025-success.json"),
            "--spec-version",
            "2025-11-25",
            "--tool-definition",
            str(TOOL_DEFINITION),
            "--json",
        ],
        cwd=REPOSITORY_ROOT,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert process.returncode == 0, process.stderr
    report = json.loads(process.stdout)
    assert report["success"] is True
    assert report["details"]["mcp_specification"] == "2025-11-25"
