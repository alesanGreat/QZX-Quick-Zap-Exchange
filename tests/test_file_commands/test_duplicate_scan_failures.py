"""A partial scan must retain useful evidence without inventing certainty."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from qzx.commands.file import _duplicate_inventory as inventory_module
from qzx.commands.file.find_duplicate_files import FindDuplicateFilesCommand


def _copies(folder, count=3, payload=b"QZX duplicate evidence" * 128):
    paths = [folder / f"copy-{index:03d}.bin" for index in range(count)]
    for path in paths:
        path.write_bytes(payload)
    return paths


def test_hash_failure_keeps_other_verified_copies_and_reports_partial(tmp_path):
    paths = _copies(tmp_path)
    original = FindDuplicateFilesCommand()._get_sha256

    def hash_with_failure(path):
        if path == str(paths[0]):
            raise PermissionError("fixture access denied")
        return original(path)

    command = FindDuplicateFilesCommand(hash_reader=hash_with_failure)
    result = command.execute(tmp_path, 0, 0)

    assert result["success"] is True
    assert result["partial"] is True
    assert result["scan_complete"] is False
    assert result["total_groups"] == 1
    assert result["total_duplicate_files"] == 2
    assert result["warning_counts"] == {"hash_failed": 1}
    assert "partial" in result["message"]
    assert str(paths[0]) == result["warnings"][0]["path"]


def test_comparison_error_is_not_silently_treated_as_different_content(tmp_path):
    _copies(tmp_path, 2)

    def unreadable_pair(*_paths):
        raise PermissionError("fixture comparison denied")

    command = FindDuplicateFilesCommand(compare_reader=unreadable_pair)
    result = command.execute(tmp_path, 0, 0)

    assert result["success"] is True
    assert result["total_groups"] == 0
    assert result["partial"] is True
    assert result["warning_counts"] == {"comparison_failed": 1}


def test_change_during_hashing_is_excluded_without_losing_other_duplicates(tmp_path):
    paths = _copies(tmp_path)
    original = FindDuplicateFilesCommand()._get_sha256

    def changing_hash(path):
        digest = original(path)
        if path == str(paths[0]):
            Path(path).write_bytes(b"changed after hashing")
        return digest

    command = FindDuplicateFilesCommand(hash_reader=changing_hash)
    result = command.execute(tmp_path, 0, 0)

    assert result["partial"] is True
    assert result["warning_counts"] == {"file_changed": 1}
    assert result["total_groups"] == 1
    group = next(iter(result["duplicate_groups"].values()))
    assert group["files"] == sorted(str(path) for path in paths[1:])


def test_change_to_an_earlier_group_is_rechecked_before_returning(tmp_path):
    earlier = _copies(tmp_path, 2, b"small")
    (tmp_path / "large-a.bin").write_bytes(b"large content" * 128)
    (tmp_path / "large-b.bin").write_bytes(b"large content" * 128)
    original = FindDuplicateFilesCommand()._get_sha256

    def change_earlier_group(path):
        if path.endswith("large-a.bin"):
            earlier[0].write_bytes(b"changed after the earlier comparison")
        return original(path)

    command = FindDuplicateFilesCommand(hash_reader=change_earlier_group)
    result = command.execute(tmp_path, 0, 0)

    assert result["partial"] is True
    assert result["total_groups"] == 1
    assert all(
        str(earlier[0]) not in group["files"]
        for group in result["duplicate_groups"].values()
    )


def test_walk_error_preserves_results_and_explicitly_marks_coverage(tmp_path):
    _copies(tmp_path, 2)
    original = inventory_module.os.walk

    def partially_readable_walk(root, **kwargs):
        yield from original(root, **kwargs)
        kwargs["onerror"](
            PermissionError(
                13, "fixture directory denied", str(tmp_path / "locked")
            )
        )

    result = FindDuplicateFilesCommand(
        walk_factory=partially_readable_walk
    ).execute(tmp_path, 0, 0)

    assert result["total_groups"] == 1
    assert result["partial"] is True
    assert result["warning_counts"] == {"directory_unreadable": 1}


def test_unreadable_root_is_a_failure_not_a_successful_empty_scan(tmp_path):
    def unreadable_walk(root, **kwargs):
        kwargs["onerror"](PermissionError(13, "fixture root denied", str(root)))
        return iter(())

    result = FindDuplicateFilesCommand(
        walk_factory=unreadable_walk
    ).execute(tmp_path, 0, 0)

    assert result["success"] is False
    assert result["error_code"] == "directory_unreadable"


def test_many_failures_have_exact_counts_and_a_bounded_warning_sample(tmp_path):
    _copies(tmp_path, 25)

    def unreadable_hash(_path):
        raise PermissionError("fixture unreadable")

    result = FindDuplicateFilesCommand(
        hash_reader=unreadable_hash
    ).execute(tmp_path, 0, 0)

    assert result["partial"] is True
    assert result["warning_count"] == 25
    assert len(result["warnings"]) == 20
    assert result["warning_sample_truncated"] is True
    assert result["warning_counts"] == {"hash_failed": 25}
    assert result["scan_statistics"]["hash_attempts"] == 25
    assert result["scan_statistics"]["files_hashed"] == 0


def test_missing_digest_is_an_explicit_issue(tmp_path):
    _copies(tmp_path, 2)
    command = FindDuplicateFilesCommand(hash_reader=lambda _path: None)
    result = command.execute(tmp_path, 0, 0)

    assert result["partial"] is True
    assert result["warning_counts"] == {"hash_failed": 2}


def test_digest_collisions_across_sizes_do_not_overwrite_verified_groups(tmp_path):
    _copies(tmp_path, 2, b"small")
    (tmp_path / "large-a.bin").write_bytes(b"large content")
    (tmp_path / "large-b.bin").write_bytes(b"large content")
    command = FindDuplicateFilesCommand(hash_reader=lambda _path: "collision")

    result = command.execute(tmp_path, 0, 0)

    assert result["total_groups"] == 2
    assert result["total_duplicate_files"] == 4
    assert result["reclaimable_bytes"] == len(b"small") + len(b"large content")
    assert set(result["duplicate_groups"]) == {"collision", "collision:2"}


@pytest.mark.parametrize("attribute", ["offline", "missing_identity"])
def test_unavailable_content_or_identity_is_explicit_not_a_false_copy(
    tmp_path, attribute
):
    paths = _copies(tmp_path, 2)
    original = inventory_module.file_snapshot

    def unavailable_snapshot(path):
        info = original(path)
        if path != str(paths[0]):
            return info
        fields = {
            name: getattr(info, name)
            for name in dir(info)
            if name.startswith("st_")
        }
        if attribute == "offline":
            fields["st_file_attributes"] = 0x1000
        else:
            fields["st_ino"] = 0
        return SimpleNamespace(**fields)

    result = FindDuplicateFilesCommand(
        snapshot_reader=unavailable_snapshot
    ).execute(tmp_path, 0, 0)

    assert result["partial"] is True
    assert result["total_groups"] == 0
    assert result["scan_statistics"]["files_hashed"] == 0


def test_unique_file_sizes_require_no_content_reads(tmp_path):
    for length in range(1, 5):
        (tmp_path / f"unique-{length}.bin").write_bytes(b"x" * length)

    def unexpected_hash(_path):
        raise AssertionError("Unique-size files should not be read")

    result = FindDuplicateFilesCommand(
        hash_reader=unexpected_hash
    ).execute(tmp_path, 0, 0)

    assert result["total_groups"] == 0
    assert result["partial"] is False
    assert result["scan_statistics"]["files_hashed"] == 0
