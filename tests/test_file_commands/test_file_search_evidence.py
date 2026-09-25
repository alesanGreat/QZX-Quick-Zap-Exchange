"""Filename search must preserve scope and report gaps instead of empty certainty."""

import pytest

from qzx.commands.file.find_files import FindFilesCommand
from qzx.commands.system.diagnose_storage import DiagnoseStorageCommand
from qzx.core import recursive_findfiles_utils as finder


def _finder_with_recursive_error(tmp_path):
    original = finder.os.walk

    def incomplete_walk(path, **kwargs):
        yield from original(path, **kwargs)
        callback = kwargs.get("onerror")
        if callback:
            callback(
                PermissionError(
                    13, "directory denied", str(tmp_path / "locked")
                )
            )

    def injected_finder(*args, **kwargs):
        return finder.find_files(
            *args, recursive_walker=incomplete_walk, **kwargs
        )

    return injected_finder


def test_recursive_directory_failure_is_exposed_in_the_result(tmp_path):
    visible = tmp_path / "visible.bin"
    visible.write_bytes(b"visible" * 256)
    result = FindFilesCommand(
        finder=_finder_with_recursive_error(tmp_path)
    ).execute(tmp_path)

    assert result["success"] is True
    assert result["count"] == 1
    assert result["partial"] is True
    assert result["scan_complete"] is False
    assert result["skipped_search_paths"] == 1
    assert result["warnings"][0]["sample_paths"] == [str(tmp_path / "locked")]
    assert "partial" in result["message"].lower()


def test_partial_filename_search_reaches_storage_without_duplicate_hashing(tmp_path):
    (tmp_path / "visible.bin").write_bytes(b"visible" * 256)
    file_search = FindFilesCommand(
        finder=_finder_with_recursive_error(tmp_path)
    )
    result = DiagnoseStorageCommand(
        find_files_command=file_search
    ).execute(
        tmp_path,
        min_file_size="1KB",
        max_depth=1,
        include_duplicates=False,
    )

    assert result["success"] is True
    assert result["partial"] is True
    assert result["probe_status"]["large_files"] == "partial"
    assert result["probe_status"]["duplicates"] == "skipped"
    assert result["assessment"]["large_files_matched"] == 1


def test_direct_unreadable_directory_is_not_a_successful_empty_search(tmp_path):
    def unreadable_finder(*_args, **_kwargs):
        raise PermissionError(13, "directory denied", str(tmp_path))
        yield  # pragma: no cover - establishes the generator boundary.

    result = FindFilesCommand(
        finder=unreadable_finder
    ).execute(tmp_path, recursive=False)

    assert result["success"] is False
    assert result["error_code"] == "search_failed"
    assert "denied" in result["message"]


def test_literal_parent_directory_with_glob_metacharacters_is_not_reinterpreted(tmp_path):
    folder = tmp_path / "assets [final]"
    folder.mkdir()
    (folder / "keep.bin").write_bytes(b"keep")

    result = FindFilesCommand().execute(folder, pattern="*.bin", recursive=False)

    assert result["success"] is True
    assert result["count"] == 1
    assert result["results"][0]["name"] == "keep.bin"


def test_shared_finder_reports_direct_errors_without_requiring_a_command(tmp_path):
    errors = []

    def denied_direct(
        directory,
        pattern,
        file_type,
        exclude_patterns,
        on_file_found,
        on_dir_found,
        on_error,
    ):
        del pattern, file_type, exclude_patterns, on_file_found, on_dir_found
        on_error(PermissionError(13, "directory denied", directory))
        return ()

    result = list(
        finder.find_files(
            str(tmp_path / "*.bin"),
            recursive=False,
            file_type="f",
            on_error=errors.append,
            direct_matcher=denied_direct,
        )
    )

    assert result == []
    assert len(errors) == 1
    assert isinstance(errors[0], PermissionError)


def test_a_display_limit_does_not_claim_an_incomplete_search(tmp_path):
    for number in range(40):
        (tmp_path / f"file-{number:02d}.bin").write_bytes(
            b"x" * (number + 1)
        )

    result = FindFilesCommand().execute(
        tmp_path, sort_by="size", descending=True, limit=3
    )

    assert result["matched_count"] == 40
    assert result["matched_size_bytes"] == sum(range(1, 41))
    assert result["count"] == 3
    assert result["total_size_bytes"] == 40 + 39 + 38
    assert result["truncated"] is True
    assert result["partial"] is False
    assert result["scan_complete"] is True
    assert [item["size_bytes"] for item in result["results"]] == [40, 39, 38]


@pytest.mark.parametrize(
    "value", [float("inf"), float("-inf"), float("nan"), "9" * 400]
)
def test_nonfinite_or_overflowing_sizes_are_user_errors_not_exceptions(
    tmp_path, value
):
    result = FindFilesCommand().execute(tmp_path, min_size=value)

    assert result["success"] is False
    assert result["error_code"] == "invalid_parameter"


@pytest.mark.parametrize("value", [1.5, True, [], float("inf")])
def test_limit_does_not_silently_truncate_or_raise(tmp_path, value):
    result = FindFilesCommand().execute(tmp_path, limit=value)

    assert result["success"] is False
    assert result["error_code"] == "invalid_parameter"


def test_same_size_results_have_deterministic_ties_when_limited(tmp_path):
    for name in ["z.bin", "a.bin", "m.bin"]:
        (tmp_path / name).write_bytes(b"same size")

    result = FindFilesCommand().execute(
        tmp_path, sort_by="size", descending=True, limit=2
    )
    repeated = FindFilesCommand().execute(
        tmp_path, sort_by="size", descending=True, limit=2
    )

    assert result["results"] == repeated["results"]
    assert len(result["results"]) == 2
