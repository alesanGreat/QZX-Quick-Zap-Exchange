#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Regression coverage for QZX Golden Core release-quality attestations."""

from __future__ import annotations

import copy

from scripts.verify_golden_core_release_quality import (
    configured_attestation_path,
    load_json,
    load_registry,
    validate_attestation,
)


def current_attestation():
    registry = load_registry()
    path = configured_attestation_path(registry)
    return registry, load_json(path, "release-quality attestation")


def test_current_release_quality_attestation_is_valid_and_git_bound():
    registry, document = current_attestation()

    assert validate_attestation(document, registry=registry, verify_git=True) == []
    assert document["status"] == "verified"
    assert document["release"]["version"] == "0.2.2.0.7a3"
    assert document["release"]["tag"] == "v0.2.2.0.7a3"
    assert len(document["commands"]) == 15
    assert document["quality_gates"]["known_release_blockers"] == []
    assert document["ci"]["environment_count"] == 10
    assert document["ci"]["command_environment_runs"] == 150
    assert document["ci"]["failed_command_runs"] == 0


def test_release_quality_rejects_stale_command_digest():
    registry, document = current_attestation()
    changed = copy.deepcopy(document)
    changed["commands"]["version"]["implementation_digest"] = "sha256:" + "0" * 64

    errors = validate_attestation(changed, registry=registry)

    assert any("stale for version" in error for error in errors)


def test_release_quality_rejects_known_release_blocker():
    registry, document = current_attestation()
    changed = copy.deepcopy(document)
    changed["quality_gates"]["known_release_blockers"] = [
        {"number": 999, "title": "Regression fixture"}
    ]
    changed["quality_gates"]["zero_known_release_blockers"] = False

    errors = validate_attestation(changed, registry=registry)

    assert any("zero_known_release_blockers" in error for error in errors)
    assert any("zero known release blockers" in error for error in errors)


def test_release_quality_rejects_tampered_attestation_hash():
    registry, document = current_attestation()
    changed = copy.deepcopy(document)
    changed["ci"]["environment_count"] = 9

    errors = validate_attestation(changed, registry=registry)

    assert any("run count is inconsistent" in error for error in errors)
    assert any("attestation SHA-256 is invalid" in error for error in errors)
