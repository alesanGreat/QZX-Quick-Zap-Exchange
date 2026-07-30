#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Read-only contract tests for project bootstrap planning."""

from qzx.commands.development.plan_project_bootstrap import (
    PlanProjectBootstrapCommand,
)


def test_explicit_plan_for_missing_project_writes_nothing(tmp_path):
    target = tmp_path / "new-project"

    result = PlanProjectBootstrapCommand().execute(
        path=target,
        tech="python",
    )

    assert result["success"] is True, result
    assert target.exists() is False
    assert result["details"]["technology"] == "python"
    assert result["details"]["technology_selection"]["method"] == "explicit"
    assert result["details"]["execution"] == {
        "read_only": True,
        "files_written": 0,
        "commands_run": 0,
        "network_requests": 0,
        "secrets_generated": 0,
    }
    assert all(
        step["qzx_will_execute"] is False
        for step in result["details"]["steps"]
    )
    assert result["details"]["summary"]["would_create"] == 3


def test_unknown_empty_project_requires_an_explicit_technology(tmp_path):
    result = PlanProjectBootstrapCommand().execute(tmp_path)

    assert result["success"] is False
    assert result["error_code"] == "technology_required"
    assert "does not silently default" in result["message"]
    assert result["details"]["files_written"] == 0


def test_mixed_manifests_fail_as_ambiguous_instead_of_guessing(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname='fixture'\n",
        encoding="utf-8",
    )
    (tmp_path / "package.json").write_text("{}\n", encoding="utf-8")

    result = PlanProjectBootstrapCommand().execute(tmp_path)

    assert result["success"] is False
    assert result["error_code"] == "ambiguous_technology"
    assert {
        item["technology"]
        for item in result["details"]["detected_candidates"]
    } == {"node", "python"}


def test_manifest_detection_is_explicit_and_read_only(tmp_path):
    manifest = tmp_path / "Cargo.toml"
    manifest.write_text("[package]\nname='fixture'\n", encoding="utf-8")
    before = manifest.read_bytes()

    result = PlanProjectBootstrapCommand().execute(
        tmp_path,
        components="environment,checks",
    )

    assert result["success"] is True, result
    assert result["details"]["technology"] == "rust"
    assert result["details"]["technology_selection"] == {
        "method": "manifest",
        "evidence": ["Cargo.toml"],
        "observed_candidates": [
            {
                "technology": "rust",
                "evidence": ["Cargo.toml"],
            }
        ],
    }
    assert result["details"]["selected_components"] == [
        "environment",
        "checks",
    ]
    assert manifest.read_bytes() == before


def test_component_selection_reports_network_and_mutation_risk(tmp_path):
    (tmp_path / "requirements.txt").write_text(
        "example-package==1.0\n",
        encoding="utf-8",
    )

    result = PlanProjectBootstrapCommand().execute(
        tmp_path,
        tech="python",
        components="dependencies,database,checks",
    )

    assert result["success"] is True, result
    steps = {
        step["component"]: step for step in result["details"]["steps"]
    }
    assert steps["dependencies"]["network"] is True
    assert steps["dependencies"]["mutates_files"] is True
    assert steps["dependencies"]["mutates_external_state"] is True
    assert steps["database"]["status"] == "not_detected"
    assert steps["checks"]["network"] is True
    assert steps["checks"]["mutates_external_state"] is True
    assert result["details"]["execution"]["commands_run"] == 0


def test_database_migration_is_sensitive_external_manual_work(tmp_path):
    (tmp_path / "manage.py").write_text(
        "raise SystemExit('must never run')\n",
        encoding="utf-8",
    )

    result = PlanProjectBootstrapCommand().execute(
        tmp_path,
        tech="python",
        components="database",
    )

    step = result["details"]["steps"][0]
    assert step["status"] == "manual_review"
    assert step["sensitive"] is True
    assert step["network"] is True
    assert step["mutates_external_state"] is True
    assert step["argv"][-2:] == ["manage.py", "migrate"]
    assert result["details"]["execution"]["commands_run"] == 0


def test_invalid_technology_and_components_fail_before_any_action(tmp_path):
    command = PlanProjectBootstrapCommand()

    invalid_tech = command.execute(tmp_path, tech="javascript")
    invalid_components = command.execute(
        tmp_path,
        tech="node",
        components="structure,install-everything",
    )

    assert invalid_tech["error_code"] == "unsupported_technology"
    assert invalid_components["error_code"] == "invalid_components"
    assert list(tmp_path.iterdir()) == []


def test_planning_logic_emits_no_unstructured_output(tmp_path, capsys):
    result = PlanProjectBootstrapCommand().execute(
        tmp_path,
        tech="cpp",
        components="structure",
    )
    captured = capsys.readouterr()

    assert result["success"] is True
    assert captured.out == ""
    assert captured.err == ""
