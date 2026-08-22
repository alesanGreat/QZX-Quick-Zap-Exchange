"""Safety, idempotency, and partial-failure tests for createDirectory."""

from __future__ import annotations

import os

from qzx.commands.file.create_directory import CreateDirectoryCommand


def _operation(result, index=0):
    return result["details"]["operations"][index]


def test_missing_paths_is_a_structured_failure():
    result = CreateDirectoryCommand().execute()

    assert result["success"] is False
    assert result["error_code"] == "missing_argument"


def test_nested_creation_reports_every_directory_actually_created(tmp_path):
    target = tmp_path / "one" / "two" / "three"

    result = CreateDirectoryCommand().invoke([str(target)])

    assert result["success"] is True
    operation = _operation(result)
    assert operation["status"] == "created"
    assert operation["changed"] is True
    assert operation["created_paths"] == [
        str(tmp_path / "one"),
        str(tmp_path / "one" / "two"),
        str(target),
    ]
    assert result["details"]["directories_created"] == 3
    assert result["details"]["directories_retained_after_command"] == 3
    assert target.is_dir()


def test_existing_directory_is_idempotent_not_misreported_as_created(tmp_path):
    target = tmp_path / "existing"
    target.mkdir()

    result = CreateDirectoryCommand().execute(target)

    assert result["success"] is True
    assert _operation(result)["status"] == "already_exists"
    assert _operation(result)["created_paths"] == []
    assert result["details"]["filesystem_changed"] is False


def test_lexical_aliases_are_deduplicated_before_mutation(tmp_path):
    target = tmp_path / "folder"
    alias = os.path.join(str(tmp_path), "unused", "..", "folder")
    mkdir_calls = []

    def recording_mkdir(path):
        mkdir_calls.append(str(path))
        os.mkdir(path)

    result = CreateDirectoryCommand(mkdir=recording_mkdir).execute(
        str(target),
        alias,
    )

    assert result["success"] is True
    assert result["details"]["duplicates"] == 1
    assert _operation(result, 1)["status"] == "duplicate"
    assert _operation(result, 1)["duplicate_of_request_index"] == 1
    assert mkdir_calls == [str(target)]


def test_conflict_does_not_hide_successful_sibling_request(tmp_path):
    conflict = tmp_path / "occupied"
    conflict.write_text("file", encoding="utf-8")
    valid = tmp_path / "created"

    result = CreateDirectoryCommand().execute(conflict, valid)

    assert result["success"] is False
    assert result["error_code"] == "partial_directory_creation"
    assert _operation(result)["error_code"] == "path_conflict"
    assert _operation(result, 1)["status"] == "created"
    assert result["details"]["failed"] == 1
    assert valid.is_dir()


def test_failed_nested_target_rolls_back_empty_ancestors(tmp_path):
    target = tmp_path / "new" / "child" / "leaf"

    def fail_at_leaf(path):
        if os.fspath(path).endswith("leaf"):
            raise PermissionError("synthetic leaf denial")
        os.mkdir(path)

    result = CreateDirectoryCommand(mkdir=fail_at_leaf).execute(target)

    assert result["success"] is False
    assert result["error_code"] == "directory_creation_failed"
    operation = _operation(result)
    assert operation["error_code"] == "directory_create_failed"
    assert operation["changed"] is False
    assert operation["created_paths"] == [
        str(tmp_path / "new"),
        str(tmp_path / "new" / "child"),
    ]
    assert operation["rolled_back_paths"] == [
        str(tmp_path / "new" / "child"),
        str(tmp_path / "new"),
    ]
    assert operation["remaining_created_paths"] == []
    assert result["details"]["directories_retained_after_command"] == 0
    assert not (tmp_path / "new").exists()


def test_symlink_parent_is_blocked_without_touching_its_target(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    link = tmp_path / "link"
    link.symlink_to(outside, target_is_directory=True)

    result = CreateDirectoryCommand().execute(link / "escaped")

    assert result["success"] is False
    operation = _operation(result)
    assert operation["error_code"] == "symlink_path_blocked"
    assert operation["blocked_component"] == str(link)
    assert not (outside / "escaped").exists()
    assert result["details"]["link_traversal_allowed"] is False


def test_raw_bytes_empty_and_nul_paths_are_independent_failures(tmp_path):
    result = CreateDirectoryCommand().execute(
        os.fsencode(tmp_path / "bytes"),
        "",
        "bad\x00path",
    )

    assert result["success"] is False
    assert result["error_code"] == "directory_creation_failed"
    assert [
        operation["error_code"] for operation in result["details"]["operations"]
    ] == [
        "invalid_directory_path",
        "invalid_directory_path",
        "invalid_directory_path",
    ]
    assert result["details"]["filesystem_changed"] is False


def test_path_batch_limit_fails_before_any_mutation(tmp_path):
    paths = [str(tmp_path / f"path-{index}") for index in range(1001)]

    result = CreateDirectoryCommand().execute(*paths)

    assert result["success"] is False
    assert result["error_code"] == "too_many_paths"
    assert result["details"]["filesystem_changed"] is False
    assert list(tmp_path.iterdir()) == []
