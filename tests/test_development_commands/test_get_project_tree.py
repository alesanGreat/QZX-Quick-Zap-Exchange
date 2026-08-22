"""Adversarial and contract tests for getProjectTree."""

from __future__ import annotations

import os
from pathlib import Path

from qzx.commands.development.get_project_tree import GetProjectTreeCommand


def _children_by_name(node):
    return {child["name"]: child for child in node["children"]}


def test_nonexistent_directory_has_stable_error_code(tmp_path):
    result = GetProjectTreeCommand().invoke([str(tmp_path / "missing")])

    assert result["success"] is False
    assert result["error_code"] == "directory_not_found"
    assert "was not found" in result["message"]


def test_file_instead_of_directory_is_rejected(tmp_path):
    file_path = tmp_path / "test.txt"
    file_path.touch()

    result = GetProjectTreeCommand().invoke([str(file_path)])

    assert result["success"] is False
    assert result["error_code"] == "not_a_directory"


def test_raw_bytes_path_is_rejected_without_a_pathlib_type_crash(tmp_path):
    result = GetProjectTreeCommand().execute(os.fsencode(tmp_path))

    assert result["success"] is False
    assert result["error_code"] == "invalid_directory_path"


def test_invalid_depth_entry_limit_and_boolean_are_not_silently_rewritten(tmp_path):
    command = GetProjectTreeCommand()

    invalid_depth = command.execute(tmp_path, max_depth="many")
    invalid_limit = command.execute(tmp_path, max_entries=0)
    invalid_boolean = command.execute(tmp_path, include_files="sometimes")

    assert invalid_depth["error_code"] == "invalid_max_depth"
    assert invalid_limit["error_code"] == "invalid_max_entries"
    assert invalid_boolean["error_code"] == "invalid_include_files"


def test_tree_is_built_once_with_deterministic_directory_first_order(tmp_path):
    (tmp_path / "z-file.txt").write_text("z", encoding="utf-8")
    (tmp_path / "a-file.txt").write_text("a", encoding="utf-8")
    child = tmp_path / "child"
    child.mkdir()
    (child / "nested.txt").write_text("nested", encoding="utf-8")
    scans = []

    def recording_scandir(path):
        scans.append(Path(path))
        return os.scandir(path)

    result = GetProjectTreeCommand(scandir=recording_scandir).execute(
        tmp_path,
        max_depth=2,
    )

    assert result["success"] is True
    assert scans == [tmp_path.absolute(), child]
    root_children = result["tree_structure"]["children"]
    assert [item["name"] for item in root_children] == [
        "child",
        "a-file.txt",
        "z-file.txt",
    ]
    assert result["details"]["entry_count"] == 4
    assert result["details"]["scan_complete"] is True
    assert result["tree_text"].count("nested.txt") == 1


def test_default_excludes_are_case_insensitive_and_custom_set_replaces_them(tmp_path):
    git_directory = tmp_path / ".GIT"
    git_directory.mkdir()
    (git_directory / "config").touch()
    source = tmp_path / "src"
    source.mkdir()

    default_result = GetProjectTreeCommand().execute(tmp_path)
    custom_result = GetProjectTreeCommand().execute(
        tmp_path,
        exclude_dirs="src",
    )

    assert ".GIT" not in default_result["tree_text"]
    assert default_result["details"]["excluded_directory_count"] == 1
    assert ".GIT" in custom_result["tree_text"]
    assert "src" not in custom_result["tree_text"]


def test_folder_only_mode_keeps_links_visible_but_never_follows_them(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("outside", encoding="utf-8")
    link = root / "external-link"
    link.symlink_to(outside, target_is_directory=True)
    (root / "ordinary.txt").write_text("inside", encoding="utf-8")

    result = GetProjectTreeCommand().execute(
        root,
        max_depth=10,
        include_files=False,
    )

    assert result["success"] is True
    assert "ordinary.txt" not in result["tree_text"]
    assert "external-link" in result["tree_text"]
    assert "secret.txt" not in result["tree_text"]
    link_node = _children_by_name(result["tree_structure"])["external-link"]
    assert link_node["type"] == "symlink"
    assert link_node["followed"] is False
    assert result["details"]["symbolic_links_followed"] is False
    assert result["details"]["symlink_count"] == 1


def test_global_entry_budget_marks_partial_output(tmp_path):
    for name in ("d.txt", "c.txt", "b.txt", "a.txt"):
        (tmp_path / name).write_text(name, encoding="utf-8")

    result = GetProjectTreeCommand().execute(tmp_path, max_entries=2)

    assert result["success"] is True
    assert result["details"]["entry_count"] == 2
    assert result["details"]["entry_limit_reached"] is True
    assert result["details"]["scan_complete"] is False
    assert "[Entry limit reached]" in result["tree_text"]
    assert [
        child["name"]
        for child in result["tree_structure"]["children"]
        if child["type"] == "file"
    ] == ["a.txt", "b.txt"]
    assert result["warnings"]


def test_nested_scan_failure_returns_partial_tree_with_bounded_evidence(tmp_path):
    blocked = tmp_path / "blocked"
    blocked.mkdir()
    (tmp_path / "visible.txt").touch()

    def selective_scandir(path):
        if Path(path) == blocked:
            raise PermissionError("synthetic access denial")
        return os.scandir(path)

    result = GetProjectTreeCommand(scandir=selective_scandir).execute(
        tmp_path,
        max_depth=2,
    )

    assert result["success"] is True
    assert result["details"]["scan_complete"] is False
    assert result["details"]["scan_error_count"] == 1
    assert result["details"]["scan_error_samples"][0]["error_type"] == (
        "PermissionError"
    )
    blocked_node = _children_by_name(result["tree_structure"])["blocked"]
    assert blocked_node["scan_error"]["error_type"] == "PermissionError"
    assert "[Scan failed: PermissionError]" in result["tree_text"]


def test_root_scan_failure_is_a_structured_command_failure(tmp_path):
    def refuse_scandir(_path):
        raise PermissionError("synthetic root denial")

    result = GetProjectTreeCommand(scandir=refuse_scandir).execute(tmp_path)

    assert result["success"] is False
    assert result["error_code"] == "directory_scan_failed"
    assert result["details"]["scan_error_count"] == 1
    assert result["tree_structure"]["scan_error"]["error_type"] == (
        "PermissionError"
    )
