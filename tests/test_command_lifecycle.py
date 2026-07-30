"""Tests for QZX's fail-closed command lifecycle contract."""

from copy import deepcopy
from pathlib import Path

import pytest

from qzx.commands.system.get_current_directory import GetCurrentDirectoryCommand
from qzx.commands.system.help import HelpCommand
from qzx.commands.system.list_commands import ListCommandsCommand
from qzx.core.command_lifecycle import (
    CommandLifecycleError,
    EXPECTED_STAGES,
    ROADMAP_STAGES,
    command_maturity,
    load_command_lifecycle,
    validate_lifecycle_evidence_files,
    validate_lifecycle_document,
    validate_lifecycle_inventory,
)
from qzx.core.command_loader import CommandLoader


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def canonical_command_names():
    """Return the exact runtime command inventory."""
    loader = CommandLoader()
    return {
        command_class.name
        for command_class in set(loader.discover_commands().values())
    }


def test_lifecycle_inventory_exactly_matches_runtime_discovery():
    names = canonical_command_names()
    document = validate_lifecycle_inventory(names)

    assert set(document["commands"]) == names
    assert set(document["stages"]) == EXPECTED_STAGES
    assert document["schema_version"] == 2
    assert document["assessment"]["established_after_version"] == "0.2.2.0.2"


def test_lifecycle_policy_and_registry_ship_with_distributions():
    manifest = (PROJECT_ROOT / "MANIFEST.in").read_text(encoding="utf-8")
    setup = (PROJECT_ROOT / "setup.py").read_text(encoding="utf-8")

    assert "include docs/command-lifecycle.md" in manifest
    assert '"resources/command-index.json"' in setup
    assert '"resources/command-lifecycle.json"' in setup


def test_roadmap_stages_cannot_be_public_commands():
    document = load_command_lifecycle()

    for stage_name in ROADMAP_STAGES | {"retired"}:
        assert document["stages"][stage_name]["public_executable"] is False
    for entry in document["commands"].values():
        assert document["stages"][entry["stage"]]["public_executable"] is True
    for entry in document["roadmap"].values():
        assert entry["stage"] in ROADMAP_STAGES


def test_promotions_above_alpha_require_a_review_with_evidence():
    document = deepcopy(load_command_lifecycle())
    document["commands"]["about"]["stage"] = "beta"

    with pytest.raises(CommandLifecycleError, match="without a promotion review"):
        validate_lifecycle_document(document)

    document["commands"]["about"]["review"] = {
        "reviewed_on": "2026-07-29",
        "rationale": "Behavior and contract reviewed for Beta.",
        "evidence": [
            "tests/test_system_commands/test_about.py",
            "docs/command-lifecycle.md",
        ],
    }

    assert validate_lifecycle_document(document) is document


def test_promotion_evidence_must_stay_repository_relative():
    document = deepcopy(load_command_lifecycle())
    document["commands"]["about"] = {
        "stage": "beta",
        "review": {
            "reviewed_on": "2026-07-29",
            "rationale": "Invalid fixture path.",
            "evidence": ["C:/private/evidence.txt"],
        },
    }

    with pytest.raises(CommandLifecycleError, match="repository-relative"):
        validate_lifecycle_document(document)


def test_promotion_review_date_requires_extended_iso_format():
    document = deepcopy(load_command_lifecycle())
    document["commands"]["about"] = {
        "stage": "beta",
        "review": {
            "reviewed_on": "20260729",
            "rationale": "Invalid date fixture.",
            "evidence": ["docs/command-lifecycle.md"],
        },
    }

    with pytest.raises(CommandLifecycleError, match="YYYY-MM-DD"):
        validate_lifecycle_document(document)


def test_promotion_evidence_files_must_exist_in_the_repository():
    repository_root = Path(__file__).resolve().parents[1]
    document = deepcopy(load_command_lifecycle())
    document["commands"]["about"] = {
        "stage": "beta",
        "review": {
            "reviewed_on": "2026-07-29",
            "rationale": "Evidence existence fixture.",
            "evidence": ["docs/command-lifecycle.md"],
        },
    }

    assert (
        validate_lifecycle_evidence_files(document, repository_root)
        is document
    )

    document["commands"]["about"]["review"]["evidence"] = [
        "tests/does-not-exist.py"
    ]
    with pytest.raises(CommandLifecycleError, match="missing files"):
        validate_lifecycle_evidence_files(document, repository_root)


def test_deprecated_command_requires_another_public_replacement():
    document = deepcopy(load_command_lifecycle())
    document["commands"]["about"] = {
        "stage": "deprecated",
        "review": {
            "reviewed_on": "2026-07-29",
            "rationale": "Migration fixture.",
            "evidence": ["docs/command-lifecycle.md"],
            "replacement": "about",
        },
    }

    with pytest.raises(CommandLifecycleError, match="another public command"):
        validate_lifecycle_document(document)


def test_inventory_validation_rejects_missing_and_obsolete_entries():
    names = canonical_command_names()

    with pytest.raises(CommandLifecycleError, match="Missing: futureCommand"):
        validate_lifecycle_inventory(names | {"futureCommand"})
    with pytest.raises(CommandLifecycleError, match="obsolete: about"):
        validate_lifecycle_inventory(names - {"about"})


def test_known_command_invocation_exposes_maturity_in_json_metadata():
    result = GetCurrentDirectoryCommand().invoke([])

    assert result["success"] is True
    assert result["meta"]["command"] == "getCurrentDirectory"
    assert result["meta"]["command_maturity"] == command_maturity(
        "getCurrentDirectory"
    )
    assert result["meta"]["command_maturity"]["stage"] == "alpha"


def test_usage_errors_keep_command_maturity_metadata():
    result = GetCurrentDirectoryCommand().invoke(
        ["true", "false", "false", "10", "extra"]
    )

    assert result["success"] is False
    assert result["error_code"] == "usage_error"
    assert result["meta"]["command_maturity"]["stage"] == "alpha"


def test_help_and_list_expose_the_same_maturity_source():
    help_result = HelpCommand().execute("getCurrentDirectory")
    list_result = ListCommandsCommand().execute("getCurrentDirectory")

    assert help_result["details"]["maturity"] == command_maturity(
        "getCurrentDirectory"
    )
    listed = list_result["commands"]["system"][0]
    assert listed["name"] == "getCurrentDirectory"
    assert listed["maturity"] == command_maturity("getCurrentDirectory")
    assert list_result["maturity_summary"] == {"alpha": 1}
    assert "getCurrentDirectory [Alpha]" in list_result["message"]
