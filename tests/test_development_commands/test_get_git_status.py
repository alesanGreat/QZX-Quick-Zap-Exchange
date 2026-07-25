#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests that run getGitStatus against the real Git executable."""

import shutil
import subprocess

from qzx.commands.development.get_git_status import GetGitStatusCommand


def _git(repository, *arguments):
    return subprocess.run(
        ["git", *arguments],
        cwd=repository,
        text=True,
        capture_output=True,
        check=True,
    )


def test_nonexistent_directory():
    result = GetGitStatusCommand().execute("non_existent_dir_xyz_123")
    assert result["success"] is False
    assert "does not exist" in result["error"]


def test_file_instead_of_directory(tmp_path):
    file_path = tmp_path / "test.txt"
    file_path.touch()
    result = GetGitStatusCommand().execute(str(file_path))
    assert result["success"] is False
    assert "is not a directory" in result["error"]


def test_real_git_reports_availability_or_a_truthful_missing_dependency(tmp_path):
    result = GetGitStatusCommand().execute(str(tmp_path))

    if shutil.which("git") is None:
        assert result["success"] is False
        assert "Git is not installed" in result["error"]
    else:
        assert result["success"] is True
        assert result["is_git_repository"] is False


def test_real_git_repository_status(tmp_path):
    if shutil.which("git") is None:
        result = GetGitStatusCommand().execute(str(tmp_path))
        assert result["success"] is False
        assert "Git is not installed" in result["error"]
        return

    _git(tmp_path, "init", "-b", "main")
    _git(tmp_path, "config", "user.name", "QZX Test")
    _git(tmp_path, "config", "user.email", "qzx-test@example.test")
    tracked = tmp_path / "tracked.txt"
    deleted = tmp_path / "deleted.txt"
    tracked.write_text("initial\n", encoding="utf-8")
    deleted.write_text("delete me\n", encoding="utf-8")
    _git(tmp_path, "add", "tracked.txt", "deleted.txt")
    _git(tmp_path, "commit", "-m", "initial")
    _git(
        tmp_path,
        "remote",
        "add",
        "origin",
        "https://example.test/qzx/repository.git",
    )

    tracked.write_text("modified\n", encoding="utf-8")
    deleted.unlink()
    staged = tmp_path / "staged.txt"
    staged.write_text("staged\n", encoding="utf-8")
    _git(tmp_path, "add", "staged.txt")
    untracked = tmp_path / "untracked.txt"
    untracked.write_text("untracked\n", encoding="utf-8")

    result = GetGitStatusCommand().execute(str(tmp_path))

    assert result["success"] is True
    assert result["is_git_repository"] is True
    assert result["branch"] == "main"
    assert result["tracking_branch"] is None
    assert result["changes_summary"] == {
        "staged_count": 1,
        "modified_count": 1,
        "untracked_count": 1,
        "deleted_count": 1,
        "total_changes": 4,
    }
    assert result["remotes"]["origin"]["fetch"].endswith("repository.git")
    assert result["recent_commits"][0]["author"] == "QZX Test"
    assert result["recent_commits"][0]["subject"] == "initial"
