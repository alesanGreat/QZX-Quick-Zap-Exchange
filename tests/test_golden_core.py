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
    "getSystemInfo",
    "getDiskSpace",
    "getRamInfo",
    "listFiles",
    "findFiles",
    "findText",
    "calculateFileHash",
    "getGitStatus",
    "diagnoseProject",
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


def test_golden_core_failure_evidence_policy_classifies_every_command():
    registry = load_golden_core()
    policy = registry["failure_evidence_policy"]
    required = policy["required_commands"]
    not_applicable = policy["not_applicable"]

    assert len(required) == len(set(required)) == 10
    assert len(not_applicable) == 5
    assert set(required).isdisjoint(not_applicable)
    assert set(required) | set(not_applicable) == set(EXPECTED_COMMANDS)
    assert all(
        item["reason"].strip() and item["reason_es"].strip()
        for item in not_applicable.values()
    )


def test_golden_core_release_quality_policy_is_fail_closed():
    registry = load_golden_core()
    policy = registry["release_quality_policy"]

    assert policy["attestation_path"] == "docs/release-quality/0.2.2.0.7a3.json"
    assert policy["blocking_issue_label"] == "release-blocker"
    assert policy["requires_exact_release_tag"] is True
    assert policy["requires_verified_distribution_hashes"] is True
    assert policy["requires_successful_ci"] is True
    assert policy["requires_digest_bound_platform_evidence"] is True
    assert policy["requires_zero_known_release_blockers"] is True
    assert policy["note"].strip()
    assert policy["note_es"].strip()


def test_golden_core_catalog_allows_alpha_commands_to_be_development_only(tmp_path):
    registry = load_golden_core()
    commands = {}
    for name in EXPECTED_COMMANDS:
        commands[name] = {
            "safety": {
                "operation": "read-only",
                "privilege_sensitive": False,
                "shares_external_data": False,
            },
            "availability": {
                "included_in_pypi": name not in {
                    "getSystemInfo",
                    "calculateFileHash",
                    "diagnoseProject",
                }
            },
        }
    catalog_path = tmp_path / "commands.json"
    catalog_path.write_text(
        json.dumps({"commands": commands}),
        encoding="utf-8",
    )

    assert validate_golden_core(registry, catalog_path=catalog_path) == []


def test_golden_core_catalog_rejects_missing_package_availability_metadata(tmp_path):
    registry = load_golden_core()
    commands = {
        name: {
            "safety": {
                "operation": "read-only",
                "privilege_sensitive": False,
                "shares_external_data": False,
            },
            "availability": {"included_in_pypi": True},
        }
        for name in EXPECTED_COMMANDS
    }
    commands["getSystemInfo"]["availability"] = {}
    catalog_path = tmp_path / "commands.json"
    catalog_path.write_text(
        json.dumps({"commands": commands}),
        encoding="utf-8",
    )

    errors = validate_golden_core(registry, catalog_path=catalog_path)

    assert any(
        "invalid package-availability metadata: getSystemInfo" in error
        for error in errors
    )
