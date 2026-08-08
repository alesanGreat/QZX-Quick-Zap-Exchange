#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Focused public-contract tests for listFiles."""

from qzx.commands.file.list_files import ListFilesCommand


def test_list_files_recurses_with_a_bounded_pattern(tmp_path):
    (tmp_path / "nested").mkdir()
    (tmp_path / "alpha.txt").write_text("alpha\n", encoding="utf-8")
    (tmp_path / "nested" / "beta.txt").write_text("beta\n", encoding="utf-8")
    (tmp_path / "ignored.log").write_text("log\n", encoding="utf-8")

    result = ListFilesCommand().invoke([str(tmp_path), "*.txt", "-r"])

    assert result["success"] is True
    assert result["directory"] == str(tmp_path)
    assert result["pattern"] == "*.txt"
    assert result["recursive"] is True
    assert [item["name"] for item in result["files"]] == [
        "alpha.txt",
        "beta.txt",
    ]
    assert all(item["is_directory"] is False for item in result["files"])
    assert result["meta"]["command"] == "listFiles"


def test_list_files_missing_directory_is_an_explicit_failure(tmp_path):
    missing = tmp_path / "missing"

    result = ListFilesCommand().invoke([str(missing), "*"])

    assert result["success"] is False
    assert result["error"] == result["message"]
    assert "not found" in result["message"]
    assert result["meta"]["schema_version"] == 1
