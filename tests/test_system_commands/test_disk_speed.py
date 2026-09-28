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


def test_disk_speed_removes_fixture_after_write_failure(tmp_path):
    def fail_fsync(_fd):
        raise OSError("synthetic fsync failure")

    result = disk_speed_workflow.execute_disk_speed(
        TestDiskSpeedCommand(),
        tmp_path,
        size_mib=1,
        fsync_fn=fail_fsync,
    )

    assert result["success"] is False
    assert result["error_code"] == "disk_benchmark_failed"
    assert list(tmp_path.iterdir()) == []


def test_disk_speed_reports_cleanup_failure_without_losing_result(tmp_path):
    def fail_fixture_unlink(path):
        raise OSError(
            f"synthetic cleanup denial for {path.name}"
        )

    result = disk_speed_workflow.execute_disk_speed(
        TestDiskSpeedCommand(),
        tmp_path,
        size_mib=1,
        unlink_fn=fail_fixture_unlink,
    )

    assert result["success"] is True
    assert result["warnings"][0]["code"] == "fixture_cleanup_failed"
    fixture = Path(result["details"]["temporary_fixture"])
    assert fixture.exists()
    fixture.unlink()
