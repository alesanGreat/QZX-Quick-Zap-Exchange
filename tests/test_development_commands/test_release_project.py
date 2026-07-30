#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Behavior and real-Git tests for releaseProject."""

import json
import stat
import subprocess
from pathlib import Path

from qzx.commands.development.release_project import ReleaseProjectCommand


def _run_git(project, *arguments):
    return subprocess.run(
        ["git", *arguments],
        cwd=project,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=15,
        check=True,
    )


def _initialize_git(project):
    _run_git(project, "init")
    _run_git(project, "config", "user.name", "QZX Test")
    _run_git(project, "config", "user.email", "qzx-test@example.invalid")
    _run_git(project, "add", "--all")
    _run_git(project, "commit", "-m", "Initial fixture")


def test_semver_and_pep440_bumping():
    command = ReleaseProjectCommand()

    assert command._bump_semver("1.2.3", "patch") == "1.2.4"
    assert command._bump_semver("1.2.3", "minor") == "1.3.0"
    assert command._bump_semver("1.2.3", "major") == "2.0.0"


def test_preview_reports_plan_without_mutating_npm_project(tmp_path):
    manifest = tmp_path / "package.json"
    original = '{"name":"fixture","version":"1.0.0"}\n'
    manifest.write_text(original, encoding="utf-8")

    result = ReleaseProjectCommand().execute(
        bump="minor",
        path=str(tmp_path),
        dry_run=True,
    )

    assert result["success"] is True
    assert result["status"] == "preview"
    assert result["changes_applied"] is False
    assert result["plan"]["old_version"] == "1.0.0"
    assert result["plan"]["new_version"] == "1.1.0"
    assert result["plan"]["ready_to_apply"] is False
    assert "create or push tags" in result["plan"]["excluded_stages"]
    assert manifest.read_text(encoding="utf-8") == original
    assert not (tmp_path / "CHANGELOG.md").exists()


def test_invalid_bump_fails_instead_of_substituting_patch(tmp_path):
    (tmp_path / "package.json").write_text(
        '{"name":"fixture","version":"1.0.0"}\n',
        encoding="utf-8",
    )

    result = ReleaseProjectCommand().execute(
        bump="surprise",
        path=str(tmp_path),
    )

    assert result["success"] is False
    assert result["error_code"] == "invalid_bump"


def test_ambiguous_manifest_requires_explicit_selection(tmp_path):
    (tmp_path / "package.json").write_text(
        '{"name":"fixture","version":"1.0.0"}\n',
        encoding="utf-8",
    )
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "fixture"\nversion = "1.0.0"\n',
        encoding="utf-8",
    )

    result = ReleaseProjectCommand().execute(path=str(tmp_path))

    assert result["success"] is False
    assert result["error_code"] == "ambiguous_manifest"
    assert len(result["details"]["manifests"]) == 2


def test_live_preparation_refuses_dirty_git_before_mutation(tmp_path):
    manifest = tmp_path / "pyproject.toml"
    original = '[project]\nname = "fixture"\nversion = "2.4.1"\n'
    manifest.write_text(original, encoding="utf-8")
    _initialize_git(tmp_path)
    (tmp_path / "unrelated.txt").write_text("user work", encoding="utf-8")

    result = ReleaseProjectCommand().execute(
        path=str(tmp_path),
        dry_run=False,
        new_version="2.4.2a1",
        release_notes="Reviewed alpha release.",
    )

    assert result["success"] is False
    assert result["error_code"] == "release_preconditions_failed"
    assert result["changes_applied"] is False
    assert manifest.read_text(encoding="utf-8") == original
    assert not (tmp_path / "CHANGELOG.md").exists()


def test_live_python_prerelease_updates_only_manifest_and_changelog(tmp_path):
    manifest = tmp_path / "pyproject.toml"
    manifest.write_bytes(
        b'[project]\r\nname = "fixture"\r\n'
        b'version = "2.4.1" # canonical\r\n'
    )
    manifest.chmod(stat.S_IRUSR | stat.S_IWUSR)
    original_mode = stat.S_IMODE(manifest.stat().st_mode)
    _initialize_git(tmp_path)

    result = ReleaseProjectCommand().execute(
        path=str(tmp_path),
        dry_run=False,
        new_version="2.4.2a1",
        release_notes="Reviewed alpha release.",
    )

    assert result["success"] is True, result
    assert result["status"] == "prepared"
    assert result["plan"]["new_version"] == "2.4.2a1"
    assert result["plan"]["transaction"]["updated_files"] == [
        str(manifest),
        str(tmp_path / "CHANGELOG.md"),
    ]
    manifest_bytes = manifest.read_bytes()
    assert b'version = "2.4.2a1" # canonical\r\n' in manifest_bytes
    assert b"\n" not in manifest_bytes.replace(b"\r\n", b"")
    assert stat.S_IMODE(manifest.stat().st_mode) == original_mode
    changelog = (tmp_path / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## [2.4.2a1]" in changelog
    assert "Reviewed alpha release." in changelog

    status = _run_git(tmp_path, "status", "--porcelain=v1").stdout.splitlines()
    assert sorted(line[3:] for line in status) == [
        "CHANGELOG.md",
        "pyproject.toml",
    ]
    assert not (tmp_path / "release").exists()


def test_public_live_preparation_creates_backup_before_writing(
    tmp_path,
    monkeypatch,
):
    project = tmp_path / "project"
    project.mkdir()
    manifest = project / "package.json"
    manifest.write_text(
        json.dumps({"name": "fixture", "version": "1.0.0"}) + "\n",
        encoding="utf-8",
    )
    backups = tmp_path / "backups"
    monkeypatch.setenv("QZX_BACKUPS_PATH", str(backups))

    result = ReleaseProjectCommand().invoke([
        "--path",
        str(project),
        "--dry-run",
        "false",
        "--new-version",
        "1.0.1",
        "--release-notes",
        "Reviewed patch release.",
        "--require-clean-git",
        "false",
    ])

    assert result["success"] is True, result
    assert result["meta"]["safety_backup"]["status"] == "created"
    assert Path(result["meta"]["safety_backup"]["path"]).is_file()
    assert json.loads(manifest.read_text(encoding="utf-8"))["version"] == "1.0.1"
