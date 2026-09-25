"""The composed storage workflow must preserve evidence, uncertainty and useful paths."""

from types import SimpleNamespace

import pytest

from qzx.commands.system.diagnose_storage import DiagnoseStorageCommand


def _probe(result):
    return SimpleNamespace(execute=lambda *_args, **_kwargs: result)


def _capacity():
    return {
        "success": True, "message": "fixture capacity",
        "disk_info": {"total_bytes": 10000, "free_bytes": 5000, "percent": 50.0},
    }


def _large_files():
    return {
        "success": True, "message": "fixture large files", "matched_count": 1,
        "count": 1, "warnings": [],
        "results": [{"path": "/fixture/large.bin", "size_bytes": 4096}],
    }


def _duplicates():
    return {
        "success": True, "message": "fixture duplicates", "total_groups": 1,
        "total_duplicate_files": 2, "reclaimable_bytes": 2048,
        "duplicate_groups": {
            "digest": {"size_bytes": 2048, "files": ["/fixture/a.bin", "/fixture/b.bin"]}
        },
        "partial": False, "warnings": [],
        "reclaimable_space_basis": "logical_content_bytes",
    }


def _command(*, capacity=None, large=None, duplicates=None):
    return DiagnoseStorageCommand(
        disk_space_command=_probe(_capacity() if capacity is None else capacity),
        find_files_command=_probe(_large_files() if large is None else large),
        duplicate_files_command=_probe(_duplicates() if duplicates is None else duplicates),
    )


def test_partial_duplicate_evidence_is_not_upgraded_to_complete(tmp_path):
    duplicates = _duplicates()
    duplicates.update(partial=True, scan_complete=False, warnings=[
        {"code": "hash_failed", "path": "/fixture/locked.bin", "message": "Denied"}
    ])

    result = _command(duplicates=duplicates).execute(tmp_path)

    assert result["success"] is True
    assert result["partial"] is True
    assert result["probe_status"]["duplicates"] == "partial"
    assert result["assessment"]["duplicate_groups"] == 1
    assert result["assessment"]["confirmed_reclaimable_bytes"] == 2048
    assert result["warnings"][0]["code"] == "hash_failed"
    assert result["warnings"][0]["probe"] == "duplicates"
    assert "partial" in result["report"].lower()
    assert "partial" in result["message"].lower()


def test_large_file_coverage_warning_marks_combined_diagnosis_partial(tmp_path):
    large = _large_files()
    large.update(skipped_unreadable=1, warnings=[
        {"code": "unreadable_files_skipped", "message": "One file was not readable."}
    ])

    result = _command(large=large).execute(tmp_path, include_duplicates=False)

    assert result["partial"] is True
    assert result["probe_status"]["large_files"] == "partial"
    assert result["probe_status"]["duplicates"] == "skipped"
    assert result["warnings"][0]["probe"] == "large_files"


def test_explicit_incomplete_probe_without_warnings_is_still_partial(tmp_path):
    duplicates = _duplicates()
    duplicates.update(scan_complete=False)

    result = _command(duplicates=duplicates).execute(tmp_path)

    assert result["partial"] is True
    assert result["probe_status"]["duplicates"] == "partial"
    assert result["warnings"]


def test_terminal_report_contains_concrete_paths_and_space_estimate_boundary(tmp_path):
    result = _command().execute(tmp_path)

    assert "/fixture/large.bin" in result["report"]
    assert "/fixture/a.bin" in result["report"]
    assert "/fixture/b.bin" in result["report"]
    assert "logical" in result["report"].lower()
    assert "not a measurement" in result["report"]
    assert result["assessment"]["reclaimable_space_basis"] == "logical_content_bytes"
    assert result["assessment"]["physical_reclaimable_bytes"] is None


def test_terminal_paths_cannot_emit_newlines_or_escape_sequences(tmp_path):
    large = _large_files()
    large["results"][0]["path"] = "/fixture/a\n\x1b[31m.bin"

    result = _command(large=large).execute(tmp_path)

    assert "/fixture/a\\x0a\\x1b[31m.bin" in result["report"]
    assert "\x1b" not in result["report"]


@pytest.mark.parametrize("name,value", [
    ("max_depth", True), ("max_depth", 1.2), ("max_files", False),
    ("duplicate_min_size_kb", 0.5),
])
def test_scope_validation_rejects_lossy_values_before_any_probe(tmp_path, name, value):
    def unexpected(*_args, **_kwargs):
        raise AssertionError("Invalid scope must not reach any probe")

    probe = SimpleNamespace(execute=unexpected)
    command = DiagnoseStorageCommand(
        disk_space_command=probe, find_files_command=probe, duplicate_files_command=probe,
    )
    result = command.execute(tmp_path, **{name: value})

    assert result["success"] is False
    assert result["error_code"] == "invalid_parameter"


@pytest.mark.parametrize("field,value", [
    ("percent", float("nan")), ("percent", float("inf")), ("percent", 101),
    ("percent", True), ("total_bytes", 0), ("free_bytes", -1),
    ("free_bytes", 10001), ("free_bytes", None),
])
def test_invalid_capacity_is_not_presented_as_a_comfortable_disk(tmp_path, field, value):
    capacity = _capacity()
    capacity["disk_info"][field] = value

    result = _command(capacity=capacity).execute(tmp_path)

    assert result["success"] is False
    assert result["error_code"] == "invalid_capacity_result"


def test_real_depth_zero_workflow_displays_all_relevant_evidence_without_writes(tmp_path):
    payload = b"read-only-storage" * 256
    (tmp_path / "first.bin").write_bytes(payload)
    (tmp_path / "second.bin").write_bytes(payload)
    before = {path.name: path.read_bytes() for path in tmp_path.iterdir()}

    result = DiagnoseStorageCommand().execute(
        tmp_path, min_file_size="1KB", duplicate_min_size_kb=0, max_depth=0,
    )

    assert result["success"] is True
    assert result["partial"] is False
    assert result["assessment"]["large_files_matched"] == 2
    assert result["assessment"]["duplicate_groups"] == 1
    assert "first.bin" in result["report"]
    assert "second.bin" in result["report"]
    assert {path.name: path.read_bytes() for path in tmp_path.iterdir()} == before
