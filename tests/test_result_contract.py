#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Regression tests for QZX Result Contract v1."""

import json
import os
import subprocess
import sys
from pathlib import Path

from qzx.core.result_contract import (
    RESULT_CONTRACT_SCHEMA_URL,
    ensure_result_contract,
    load_result_contract_schema,
    result_contract_violations,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = (
    REPOSITORY_ROOT
    / "src"
    / "qzx"
    / "resources"
    / "schemas"
    / "result-contract-v1.schema.json"
)
VALIDATOR_PATH = REPOSITORY_ROOT / "scripts" / "validate_result_contract.py"


def run_cli(*arguments):
    environment = os.environ.copy()
    environment["QZX_TELEMETRY"] = "0"
    environment["PYTHONPATH"] = str(REPOSITORY_ROOT / "src")
    return subprocess.run(
        [sys.executable, "-m", "qzx", *arguments],
        cwd=REPOSITORY_ROOT,
        env=environment,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )


def test_packaged_schema_identifies_the_public_contract():
    schema = load_result_contract_schema()
    assert schema == json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert schema["$id"] == RESULT_CONTRACT_SCHEMA_URL
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["required"] == ["success", "message"]
    assert schema["properties"]["success"]["type"] == "boolean"
    assert schema["properties"]["message"]["minLength"] == 1
    assert schema["properties"]["message"]["pattern"] == r"\S"
    assert schema["properties"]["error"]["pattern"] == r"\S"
    assert schema["properties"]["warnings"]["items"]["pattern"] == r"\S"
    assert schema["properties"]["meta"]["properties"]["command"]["pattern"] == r"\S"
    success_rule = schema["allOf"][1]
    assert success_rule["if"]["properties"]["success"]["const"] is True
    assert success_rule["then"]["not"]["anyOf"] == [
        {"required": ["error"]},
        {"required": ["error_code"]},
    ]
    assert schema["additionalProperties"] is True


def test_core_validator_accepts_additive_success_and_failure_results():
    success = {
        "success": True,
        "message": "Inspection completed.",
        "items": ["one", "two"],
        "meta": {
            "command": "fixture",
            "duration_ms": 1.25,
            "schema_version": 1,
            "producer_specific": "kept",
        },
    }
    failure = {
        "success": False,
        "message": "The fixture failed.",
        "error_code": "fixture_failed",
        "details": {"remediation": "Retry with a valid fixture."},
    }

    assert result_contract_violations(success) == []
    assert result_contract_violations(failure) == []
    assert ensure_result_contract(success) is success


def test_core_validator_rejects_ambiguous_documents():
    assert result_contract_violations([]) == [
        "The result must be a JSON object."
    ]

    violations = result_contract_violations(
        {
            "success": "yes",
            "message": "   ",
            "error_code": "Bad-Code",
            "warnings": ["   "],
            "meta": {
                "schema_version": 2,
                "command": "   ",
                "duration_ms": float("inf"),
            },
        }
    )
    assert "success must be a boolean." in violations
    assert "message must be a non-empty string." in violations
    assert "error_code must use lower_snake_case when present." in violations
    assert "Every warnings item must be a non-empty string." in violations
    assert "meta.schema_version must equal 1." in violations
    assert "meta.command must be a non-empty string when present." in violations
    assert "meta.duration_ms must be a finite non-negative number." in violations


def test_core_validator_rejects_failure_fields_on_success():
    expected = [
        "A successful result must not include error or error_code."
    ]
    assert result_contract_violations(
        {
            "success": True,
            "message": "The operation completed.",
            "error": "Stale failure text.",
        }
    ) == expected
    assert result_contract_violations(
        {
            "success": True,
            "message": "The operation completed.",
            "error_code": "stale_failure",
        }
    ) == expected


def test_core_validator_rejects_explicit_null_for_typed_optional_fields():
    assert result_contract_violations(
        {
            "success": True,
            "message": "The operation completed.",
            "details": None,
            "warnings": None,
            "meta": None,
        }
    ) == [
        "details must be an object when present.",
        "warnings must be an array when present.",
        "meta must be an object when present.",
    ]

    assert result_contract_violations(
        {
            "success": True,
            "message": "The operation completed.",
            "meta": {
                "schema_version": None,
                "command": None,
                "duration_ms": None,
                "command_maturity": None,
            },
        }
    ) == [
        "meta.schema_version must equal 1.",
        "meta.command must be a non-empty string when present.",
        "meta.duration_ms must be a finite non-negative number.",
        "meta.command_maturity must be an object when present.",
    ]


def test_invalid_internal_result_is_replaced_by_a_conforming_failure():
    replacement = ensure_result_contract({"success": False, "message": ""})
    assert replacement["success"] is False
    assert replacement["error_code"] == "invalid_result_contract"
    assert replacement["meta"]["schema_version"] == 1
    assert result_contract_violations(replacement) == []


def test_real_cli_success_and_failure_conform():
    successful = run_cli(
        "getCurrentDateTime",
        "--output-format",
        "iso",
        "--json",
    )
    assert successful.returncode == 0, successful.stderr
    successful_document = json.loads(successful.stdout)
    assert result_contract_violations(successful_document) == []

    failed = run_cli("definitelyMissingCommand", "--json")
    assert failed.returncode == 127, failed.stderr
    failed_document = json.loads(failed.stdout)
    assert result_contract_violations(failed_document) == []


def test_standalone_validator_supports_stdin_and_json_reports():
    document = {
        "success": True,
        "message": "Standalone validation fixture.",
    }
    process = subprocess.run(
        [sys.executable, str(VALIDATOR_PATH), "-", "--json"],
        cwd=REPOSITORY_ROOT,
        input=json.dumps(document),
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert process.returncode == 0, process.stderr
    report = json.loads(process.stdout)
    assert report["success"] is True
    assert report["details"]["contract"] == RESULT_CONTRACT_SCHEMA_URL
    assert report["details"]["violations"] == []
