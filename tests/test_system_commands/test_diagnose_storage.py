"""Focused product-contract tests for diagnoseStorage."""

from qzx.commands.system.diagnose_storage import DiagnoseStorageCommand


class RecordingProbe:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def execute(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.result


class FailingIfCalledProbe:
    def execute(self, *args, **kwargs):  # pragma: no cover - failure explains itself
        raise AssertionError("Probe should not have been called")


def _capacity_result(percent=92.5):
    return {
        "success": True,
        "message": "capacity ok",
        "disk_info": {
            "path": "/fixture",
            "total_bytes": 1_000_000,
            "used_bytes": 925_000,
            "free_bytes": 75_000,
            "total": "976.56 KB",
            "used": "903.32 KB",
            "free": "73.24 KB",
            "percent": percent,
        },
    }


def _large_files_result():
    return {
        "success": True,
        "message": "large files ok",
        "matched_count": 3,
        "count": 2,
        "warnings": [],
        "results": [
            {"path": "/fixture/big.bin", "size_bytes": 300_000},
            {"path": "/fixture/other.bin", "size_bytes": 200_000},
        ],
    }


def _duplicates_result():
    return {
        "success": True,
        "message": "duplicates ok",
        "total_groups": 1,
        "total_duplicate_files": 2,
        "reclaimable_bytes": 200_000,
        "reclaimable_space_readable": "195.31 KB",
        "duplicate_groups": {
            "digest": {
                "files": ["/fixture/a.bin", "/fixture/b.bin"],
                "size_bytes": 200_000,
            }
        },
    }


def test_diagnose_storage_combines_evidence_and_never_claims_large_files_reclaimable(
    tmp_path,
):
    capacity = RecordingProbe(_capacity_result())
    large_files = RecordingProbe(_large_files_result())
    duplicates = RecordingProbe(_duplicates_result())
    command = DiagnoseStorageCommand(
        disk_space_command=capacity,
        find_files_command=large_files,
        duplicate_files_command=duplicates,
    )

    result = command.execute(
        str(tmp_path),
        min_file_size="100MiB",
        max_files=2,
        duplicate_min_size_kb=10240,
        max_depth=5,
    )

    assert result["success"] is True
    assert result["partial"] is False
    assert result["read_only"] is True
    assert result["assessment"]["capacity_status"] == "critical"
    assert result["assessment"]["large_files_matched"] == 3
    assert result["assessment"]["confirmed_reclaimable_bytes"] == 200_000
    assert result["probe_status"] == {
        "capacity": "ok",
        "large_files": "ok",
        "duplicates": "ok",
    }
    assert "QZX did not delete or modify any files" in result["message"]
    assert "195.31 KB reclaimable" in result["report"]
    assert capacity.calls[0][0] == (str(tmp_path.resolve()),)
    assert large_files.calls[0][1]["recursive"] == 5
    assert large_files.calls[0][1]["sort_by"] == "size"
    assert large_files.calls[0][1]["descending"] is True
    assert duplicates.calls[0][1]["max_depth"] == 5


def test_diagnose_storage_can_skip_duplicate_hashing(tmp_path):
    command = DiagnoseStorageCommand(
        disk_space_command=RecordingProbe(_capacity_result(percent=55)),
        find_files_command=RecordingProbe(_large_files_result()),
        duplicate_files_command=FailingIfCalledProbe(),
    )

    result = command.execute(str(tmp_path), include_duplicates=False)

    assert result["success"] is True
    assert result["partial"] is False
    assert result["probe_status"]["duplicates"] == "skipped"
    assert result["duplicates"] is None
    assert result["assessment"]["confirmed_reclaimable_bytes"] == 0
    assert any(
        "--include-duplicates true" in item["action"]
        for item in result["recommendations"]
    )


def test_diagnose_storage_preserves_useful_partial_result_when_duplicates_fail(
    tmp_path,
):
    duplicate_failure = RecordingProbe(
        {
            "success": False,
            "message": "A file became unreadable during hashing.",
        }
    )
    command = DiagnoseStorageCommand(
        disk_space_command=RecordingProbe(_capacity_result(percent=82)),
        find_files_command=RecordingProbe(_large_files_result()),
        duplicate_files_command=duplicate_failure,
    )

    result = command.execute(str(tmp_path))

    assert result["success"] is True
    assert result["partial"] is True
    assert result["assessment"]["capacity_status"] == "attention"
    assert result["probe_status"]["duplicates"] == "failed"
    assert result["warnings"][-1]["code"] == "duplicate_scan_failed"
    assert "partial" in result["message"].lower()


def test_diagnose_storage_fails_closed_when_capacity_or_large_file_probe_fails(
    tmp_path,
):
    capacity_failure = RecordingProbe(
        {"success": False, "message": "capacity unavailable"}
    )
    command = DiagnoseStorageCommand(
        disk_space_command=capacity_failure,
        find_files_command=FailingIfCalledProbe(),
        duplicate_files_command=FailingIfCalledProbe(),
    )

    result = command.execute(str(tmp_path))

    assert result["success"] is False
    assert result["error_code"] == "capacity_probe_failed"
    assert result["details"]["probe"] == "capacity"

    large_failure = RecordingProbe(
        {"success": False, "message": "large-file scan unavailable"}
    )
    command = DiagnoseStorageCommand(
        disk_space_command=RecordingProbe(_capacity_result()),
        find_files_command=large_failure,
        duplicate_files_command=FailingIfCalledProbe(),
    )

    result = command.execute(str(tmp_path))

    assert result["success"] is False
    assert result["error_code"] == "large_files_probe_failed"
    assert result["details"]["probe"] == "large_files"


def test_diagnose_storage_validates_scope_before_probing(tmp_path):
    command = DiagnoseStorageCommand(
        disk_space_command=FailingIfCalledProbe(),
        find_files_command=FailingIfCalledProbe(),
        duplicate_files_command=FailingIfCalledProbe(),
    )

    missing = command.execute(str(tmp_path / "missing"))
    assert missing["success"] is False
    assert missing["error_code"] == "path_not_found"

    source = tmp_path / "file.txt"
    source.write_text("x", encoding="utf-8")
    not_directory = command.execute(str(source))
    assert not_directory["success"] is False
    assert not_directory["error_code"] == "not_a_directory"

    invalid_depth = command.execute(str(tmp_path), max_depth=65)
    assert invalid_depth["success"] is False
    assert invalid_depth["error_code"] == "invalid_parameter"

    invalid_bool = command.execute(str(tmp_path), include_duplicates="sometimes")
    assert invalid_bool["success"] is False
    assert invalid_bool["error_code"] == "invalid_parameter"


def test_diagnose_storage_real_read_only_workflow_finds_large_and_duplicate_files(
    tmp_path,
):
    first = tmp_path / "first.bin"
    second = tmp_path / "second.bin"
    unique = tmp_path / "unique.bin"
    payload = b"QZX-storage-diagnostic\n" * 1024
    first.write_bytes(payload)
    second.write_bytes(payload)
    unique.write_bytes(b"unique\n" * 1024)

    before = {
        path.name: path.read_bytes()
        for path in (first, second, unique)
    }

    result = DiagnoseStorageCommand().execute(
        str(tmp_path),
        min_file_size="1KB",
        max_files=10,
        duplicate_min_size_kb=1,
        max_depth=2,
        include_duplicates=True,
    )

    assert result["success"] is True
    assert result["read_only"] is True
    assert result["assessment"]["large_files_matched"] == 3
    assert result["assessment"]["duplicate_groups"] == 1
    assert result["assessment"]["confirmed_reclaimable_bytes"] == len(payload)
    assert {
        path.name: path.read_bytes()
        for path in (first, second, unique)
    } == before
