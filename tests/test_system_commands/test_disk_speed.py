from pathlib import Path

import qzx.commands.system._disk_speed_workflow as disk_speed_workflow
from qzx.commands.system.test_disk_speed import TestDiskSpeedCommand


def test_disk_speed_uses_and_removes_a_unique_fixture(tmp_path):
    result = TestDiskSpeedCommand().execute(tmp_path, size_mib=1)

    assert result["success"] is True
    assert result["fixture_size"]["bytes"] == 1024 * 1024
    assert result["write"]["mebibytes_per_second"] > 0
    assert result["read"]["bytes_verified"] == 1024 * 1024
    assert list(tmp_path.iterdir()) == []


def test_disk_speed_rejects_unbounded_fixture_sizes(tmp_path):
    result = TestDiskSpeedCommand().execute(tmp_path, size_mib=2048)

    assert result["success"] is False
    assert result["error_code"] == "invalid_size_mib"
    assert list(tmp_path.iterdir()) == []


def test_disk_speed_removes_fixture_after_write_failure(tmp_path, monkeypatch):
    def fail_fsync(_fd):
        raise OSError("synthetic fsync failure")

    monkeypatch.setattr(disk_speed_workflow.os, "fsync", fail_fsync)

    result = TestDiskSpeedCommand().execute(tmp_path, size_mib=1)

    assert result["success"] is False
    assert result["error_code"] == "disk_benchmark_failed"
    assert list(tmp_path.iterdir()) == []


def test_disk_speed_reports_cleanup_failure_without_losing_result(
    tmp_path,
    monkeypatch,
):
    original_unlink = Path.unlink

    def fail_fixture_unlink(path, *args, **kwargs):
        if path.name.startswith(".qzx-disk-speed-"):
            raise OSError("synthetic cleanup denial")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_fixture_unlink)

    result = TestDiskSpeedCommand().execute(tmp_path, size_mib=1)

    assert result["success"] is True
    assert result["warnings"][0]["code"] == "fixture_cleanup_failed"
    fixture = Path(result["details"]["temporary_fixture"])
    assert fixture.exists()
    original_unlink(fixture)
