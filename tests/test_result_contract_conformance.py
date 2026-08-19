#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Regression tests for the QZX Result Contract v1 conformance fixtures."""

import json
from pathlib import Path

import pytest

from scripts.run_result_contract_conformance import (
    DEFAULT_MANIFEST,
    run_conformance,
)


def test_reference_conformance_suite_passes_positive_and_negative_cases():
    manifest = json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8"))
    expected_positive = sum(
        1 for case in manifest["cases"] if case["expected_conformant"] is True
    )
    expected_negative = sum(
        1 for case in manifest["cases"] if case["expected_conformant"] is False
    )
    result = run_conformance()

    assert result["success"] is True
    assert result["details"]["case_count"] == len(manifest["cases"])
    assert result["details"]["positive_count"] == expected_positive
    assert result["details"]["negative_count"] == expected_negative
    assert result["details"]["failed_count"] == 0
    assert all(case["passed"] for case in result["details"]["cases"])


def test_conformance_suite_detects_a_validator_expectation_mismatch(tmp_path):
    source_directory = DEFAULT_MANIFEST.parent
    for source in source_directory.glob("*.json"):
        (tmp_path / source.name).write_bytes(source.read_bytes())
    manifest_path = tmp_path / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["cases"][2]["expected_violations"] = ["invented violation"]
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    result = run_conformance(manifest_path)

    assert result["success"] is False
    assert result["details"]["failed_count"] == 1
    failed = [case for case in result["details"]["cases"] if not case["passed"]]
    assert failed[0]["id"] == "invalid_missing_message"
    assert failed[0]["actual_violations"] == [
        "message must be a non-empty string."
    ]


def test_conformance_manifest_cannot_escape_its_directory(tmp_path):
    outside = tmp_path / "outside.json"
    outside.write_text('{"success":true,"message":"ok"}\n', encoding="utf-8")
    manifest_directory = tmp_path / "suite"
    manifest_directory.mkdir()
    manifest_path = manifest_directory / "manifest.json"
    manifest_path.write_text(
        json.dumps({
            "schema_version": 1,
            "contract": (
                "https://qzx.yumbale.com/schemas/"
                "result-contract-v1.schema.json"
            ),
            "cases": [{
                "id": "escape",
                "file": "../outside.json",
                "expected_conformant": True,
                "expected_violations": [],
            }],
        }),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="escapes the manifest directory"):
        run_conformance(manifest_path)


def test_every_manifest_case_file_exists_and_is_valid_json():
    manifest = json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8"))

    for case in manifest["cases"]:
        path = Path(DEFAULT_MANIFEST.parent, case["file"])
        assert path.is_file()
        json.loads(path.read_text(encoding="utf-8"))


def test_conformance_runner_rejects_duplicate_manifest_members(tmp_path):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        '{"schema_version":1,"schema_version":1,"cases":[]}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Duplicate JSON object member name"):
        run_conformance(manifest_path)
