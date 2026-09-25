"""Focused deterministic tests for changePermissions."""

from __future__ import annotations

import os

from qzx.commands.file.change_permissions import ChangePermissionsCommand


def test_change_permissions_updates_single_file_through_injected_chmod(tmp_path):
    target = tmp_path / "sample.txt"
    target.write_text("content", encoding="utf-8")
    calls = []

    def record_chmod(path, mode):
        calls.append((os.path.abspath(path), mode))

    result = ChangePermissionsCommand(chmod=record_chmod).execute(
        str(target),
        "640",
    )

    assert result["success"] is True
    assert result["type"] == "file"
    assert result["mode"] == "640"
    assert result["recursive"] == 0
    assert calls == [(os.path.abspath(target), 0o640)]


def test_change_permissions_missing_path_is_non_mutating(tmp_path):
    calls = []

    def record_chmod(path, mode):
        calls.append((path, mode))

    result = ChangePermissionsCommand(chmod=record_chmod).execute(
        str(tmp_path / "missing"),
        "700",
    )

    assert result["success"] is False
    assert "does not exist" in result["error"]
    assert calls == []


def test_change_permissions_symbolic_mode_is_rejected_before_mutation(tmp_path):
    target = tmp_path / "sample.txt"
    target.write_text("content", encoding="utf-8")
    calls = []

    def record_chmod(path, mode):
        calls.append((path, mode))

    result = ChangePermissionsCommand(chmod=record_chmod).execute(
        str(target),
        "u+x",
    )

    assert result["success"] is False
    assert "not supported" in result["error"]
    assert calls == []


def test_change_permissions_recursive_warning_does_not_abort_other_entries(tmp_path):
    nested = tmp_path / "nested"
    nested.mkdir()
    source = nested / "sample.txt"
    source.write_text("content", encoding="utf-8")
    calls = []

    def selective_chmod(path, mode):
        absolute = os.path.abspath(path)
        if absolute == os.path.abspath(source):
            raise PermissionError("synthetic denial")
        calls.append((absolute, mode))

    result = ChangePermissionsCommand(chmod=selective_chmod).execute(
        str(tmp_path),
        "700",
        "-r",
    )

    assert result["success"] is True
    assert result["items_modified"] == 2
    assert len(result["warnings"]) == 1
    assert "synthetic denial" in result["warnings"][0]
    assert {path for path, _ in calls} == {
        os.path.abspath(tmp_path),
        os.path.abspath(nested),
    }
