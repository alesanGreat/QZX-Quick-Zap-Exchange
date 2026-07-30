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
