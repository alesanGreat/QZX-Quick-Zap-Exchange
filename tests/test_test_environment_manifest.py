"""Focused manifest validation contracts for sync_test_environments."""

from copy import deepcopy

import pytest

from scripts import sync_test_environments as sync


def test_current_test_environment_manifest_validates_without_workflow_io():
    manifest = sync.load_manifest()

    sync.validate_manifest(manifest, validate_workflows=False)


def test_test_environment_manifest_rejects_run_result_fields():
    manifest = deepcopy(sync.load_manifest())
    manifest["environments"][0]["status"] = "passed"

    with pytest.raises(ValueError, match="run-result fields"):
        sync.validate_manifest(manifest, validate_workflows=False)


def test_test_environment_manifest_rejects_duplicate_environment_ids():
    manifest = deepcopy(sync.load_manifest())
    manifest["environments"][1]["id"] = manifest["environments"][0]["id"]

    with pytest.raises(ValueError, match="Duplicate test environment id"):
        sync.validate_manifest(manifest, validate_workflows=False)


def test_test_environment_manifest_requires_exact_summary_fields():
    manifest = deepcopy(sync.load_manifest())
    manifest["summary_templates"]["en"] = "{platforms} {python} {extra}"

    with pytest.raises(ValueError, match="must use exactly"):
        sync.validate_manifest(manifest, validate_workflows=False)
