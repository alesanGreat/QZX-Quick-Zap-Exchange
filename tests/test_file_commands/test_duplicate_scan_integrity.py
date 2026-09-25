"""Storage evidence must describe the requested scope, not silently lose files."""

import os

import pytest

from qzx.commands.file.find_duplicate_files import FindDuplicateFilesCommand


def _pair(folder, payload=b"same content" * 256):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "a.bin").write_bytes(payload)
    (folder / "b.bin").write_bytes(payload)
    return payload


def test_depth_zero_includes_files_in_the_requested_directory(tmp_path):
    payload = _pair(tmp_path)
    _pair(tmp_path / "child", b"child" * 1024)

    result = FindDuplicateFilesCommand().execute(tmp_path, 0, 0)

    assert result["success"] is True
    assert result["total_groups"] == 1
    assert result["reclaimable_bytes"] == len(payload)
    paths = next(iter(result["duplicate_groups"].values()))["files"]
    assert set(paths) == {str(tmp_path / "a.bin"), str(tmp_path / "b.bin")}


def test_depth_boundary_is_inclusive_and_does_not_visit_grandchildren(tmp_path):
    _pair(tmp_path)
    _pair(tmp_path / "child", b"child" * 1024)
    _pair(tmp_path / "child" / "grandchild", b"grandchild" * 1024)

    result = FindDuplicateFilesCommand().execute(tmp_path, 0, 1)

    assert result["total_groups"] == 2
    assert all(
        "grandchild" not in path
        for group in result["duplicate_groups"].values()
        for path in group["files"]
    )


def test_hardlink_alias_is_not_an_independent_reclaimable_copy(tmp_path):
    payload = _pair(tmp_path)
    os.link(tmp_path / "a.bin", tmp_path / "alias.bin")

    result = FindDuplicateFilesCommand().execute(tmp_path, 0, 1)

    assert result["total_groups"] == 1
    assert result["total_duplicate_files"] == 2
    assert result["reclaimable_bytes"] == len(payload)
    assert result["hardlink_aliases"] == [
        {"path": str(tmp_path / "alias.bin"), "same_file_as": str(tmp_path / "a.bin")}
    ]
    assert result["reclaimable_space_basis"] == "logical_content_bytes"
    assert result["physical_reclaimable_bytes"] is None


def test_only_hardlink_aliases_do_not_form_a_duplicate_group(tmp_path):
    (tmp_path / "a.bin").write_bytes(b"content" * 256)
    os.link(tmp_path / "a.bin", tmp_path / "alias.bin")

    result = FindDuplicateFilesCommand().execute(tmp_path, 0, 1)

    assert result["total_groups"] == 0
    assert result["reclaimable_bytes"] == 0
    assert result["scan_statistics"]["files_hashed"] == 0


@pytest.mark.parametrize("value", ["NaN", "inf", "-inf", "bad", -1, None, True])
def test_invalid_size_threshold_is_rejected_instead_of_using_a_hidden_default(
    tmp_path, value
):
    _pair(tmp_path)

    result = FindDuplicateFilesCommand().execute(tmp_path, value, 1)

    assert result["success"] is False
    assert result["error_code"] == "invalid_parameter"
    assert "min_size_kb" in result["message"]


@pytest.mark.parametrize("value", [-1, 65, "bad", None, True, 1.5])
def test_invalid_depth_is_rejected_before_scanning(tmp_path, value):
    _pair(tmp_path)

    result = FindDuplicateFilesCommand().execute(tmp_path, 0, value)

    assert result["success"] is False
    assert result["error_code"] == "invalid_parameter"
    assert "max_depth" in result["message"]


def test_empty_files_are_valid_duplicates_with_zero_redundant_bytes(tmp_path):
    _pair(tmp_path, b"")

    result = FindDuplicateFilesCommand().execute(tmp_path, 0, 0)

    assert result["total_groups"] == 1
    assert result["reclaimable_bytes"] == 0
    assert result["partial"] is False
    assert result["scan_complete"] is True
