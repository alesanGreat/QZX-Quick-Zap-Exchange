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
        assert details["backcompat_text_matches"] is True


def test_is_error_must_match_qzx_success():
    violations, warnings, details = validator.validate_mcp_profile(
        load_fixture("mcp-invalid-is-error.json")
    )
    assert (
        "isError must equal !structuredContent.success for a completed QZX MCP "
        "profile result."
    ) in violations
    assert warnings == []
    assert details["backcompat_text_matches"] is True


def test_protocol_error_is_not_a_completed_qzx_result():
    violations, warnings, details = validator.validate_mcp_profile(
        load_fixture("mcp-protocol-error.json")
    )
    assert violations == [
        "MCP protocol errors are not completed QZX Result Contract results."
    ]
    assert warnings == []
    assert details["backcompat_text_matches"] is False


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
