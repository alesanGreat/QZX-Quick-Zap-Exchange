#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for the token-saving getCurrentDirectory filesystem summary."""

from qzx.commands.system.get_current_directory import GetCurrentDirectoryCommand


def _build_directory(directory):
    (directory / "alpha.txt").write_bytes(b"abc")
    (directory / "LICENSE").write_bytes(b"xy")
    (directory / ".secret").write_bytes(b"s")
    (directory / "child").mkdir()
    (directory / "child" / "nested.py").write_bytes(b"python")
    (directory / "empty").mkdir()
    (directory / "pyproject.toml").write_bytes(b"[project]")


def test_default_reports_only_current_level_counts(tmp_path, monkeypatch):
    _build_directory(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = GetCurrentDirectoryCommand().invoke([])

    assert result["success"] is True
    assert result["current_dir"] == str(tmp_path)
    assert result["contents"] == {
        "scope": "current_level",
        "entry_count": 6,
        "file_count": 4,
        "directory_count": 2,
        "symlink_count": 0,
        "other_count": 0,
        "hidden_count": 1,
        "is_empty": False,
        "immediate_files_size_bytes": 15,
        "immediate_files_size_formatted": "15 B",
        "detected_project_markers": ["pyproject.toml"],
        "scan_complete": True,
        "scan_error_count": 0,
    }
    assert "recursive_analysis" not in result
    assert "4 files, 2 directories" in result["message"]


def test_size_adds_recursive_totals_without_detail_lists(
    tmp_path,
    monkeypatch,
):
    _build_directory(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = GetCurrentDirectoryCommand().invoke(["--size"])
    recursive = result["recursive_analysis"]

    assert result["success"] is True
    assert recursive["file_count"] == 5
    assert recursive["directory_count"] == 2
    assert recursive["total_size_bytes"] == 21
    assert recursive["total_size_formatted"] == "21 B"
    assert recursive["symbolic_links_followed"] is False
    assert "extensions" not in recursive
    assert "largest_files" not in recursive


def test_details_reuses_scan_for_previews_and_aggregates(
    tmp_path,
    monkeypatch,
):
    _build_directory(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = GetCurrentDirectoryCommand().invoke(
        ["--details", "--limit", "2"],
    )
    contents = result["contents"]
    recursive = result["recursive_analysis"]

    assert result["success"] is True
    assert contents["entry_preview_count"] == 2
    assert contents["entry_preview_truncated"] is True
    assert [item["name"] for item in contents["entry_preview"]] == [
        "child",
        "empty",
    ]
    assert recursive["file_count"] == 5
    assert recursive["total_size_bytes"] == 21
    assert len(recursive["extensions"]) == 2
    assert recursive["extensions_truncated"] is True
    assert len(recursive["largest_files"]) == 2
    assert recursive["largest_files"][0]["relative_path"] == "pyproject.toml"
    assert len(recursive["recently_modified_files"]) == 2
    assert result["directory"]["writable"] is True
    assert result["filesystem"]["total_bytes"] > 0


def test_full_option_can_show_only_the_directory_name(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)

    result = GetCurrentDirectoryCommand().invoke(["--full", "false"])

    assert result["success"] is True
    assert result["full_path"] is False
    assert result["displayed_path"] == tmp_path.name
    assert result["current_dir"] == str(tmp_path)


def test_limit_validation_is_structured(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = GetCurrentDirectoryCommand().invoke(
        ["--details", "--limit", "0"]
    )

    assert result["success"] is False
    assert result["error_code"] == "invalid_limit"
    assert result["details"]["minimum"] == 1
    assert result["details"]["maximum"] == 100
