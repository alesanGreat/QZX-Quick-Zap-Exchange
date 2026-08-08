#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Regression tests for the public QZX Golden Core candidate registry."""

import json
from importlib.resources import files

from scripts.verify_golden_core import (
    load_golden_core,
    validate_golden_core,
)


EXPECTED_COMMANDS = [
    "version",
    "listCommands",
    "help",
    "getCurrentDateTime",
    "getCurrentDirectory",
    "systemInfo",
    "getDiskSpace",
    "getRamInfo",
    "listFiles",
    "findFiles",
    "findText",
    "getFileHash",
    "getGitStatus",
    "projectDoctor",
    "checkUrlStatus",
]


def test_golden_core_registry_is_valid_and_deliberately_still_candidate():
    registry = load_golden_core()

    assert validate_golden_core(registry) == []
    assert registry["status"] == "candidate"
    assert registry["target_maturity"] == "beta"
    assert [item["name"] for item in registry["commands"]] == EXPECTED_COMMANDS
    assert "not a separate edition" in registry["disclaimer"]
    assert "external adoption" in registry["disclaimer"]
    assert "cohorte de enfoque" in registry["disclaimer_es"]
    assert all(
        item["rationale"] and item["rationale_es"]
        for item in registry["commands"]
    )
    assert all(
        principle["en"] and principle["es"]
        for principle in registry["selection_principles"]
    )


def test_golden_core_registry_is_shipped_as_a_package_resource():
    resource = files("qzx.resources").joinpath("golden-core.json")

    assert resource.is_file()
    packaged = json.loads(resource.read_text(encoding="utf-8"))
    assert packaged == load_golden_core()


def test_golden_core_rejects_duplicates_and_unexplained_entries():
    registry = load_golden_core()
    registry["commands"] = [dict(item) for item in registry["commands"]]
    registry["commands"][1]["name"] = registry["commands"][0]["name"]
    registry["commands"][1]["rationale"] = "too short"

    errors = validate_golden_core(registry)

    assert any("duplicated" in error for error in errors)
    assert any("rationale" in error for error in errors)


def test_golden_core_readiness_dimensions_are_complete_and_unique():
    registry = load_golden_core()
    dimension_ids = [item["id"] for item in registry["readiness_dimensions"]]

    assert len(dimension_ids) == len(set(dimension_ids)) == 8
    assert set(dimension_ids) == {
        "behavioral_tests",
        "policy_review",
        "success_evidence",
        "failure_evidence",
        "result_contract_review",
        "platform_evidence",
        "release_quality",
        "lifecycle_review",
    }
