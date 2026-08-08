#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Focused public-contract tests for getDiskSpace."""

from types import SimpleNamespace

from qzx.commands.system.get_disk_space import GetDiskSpaceCommand


def test_get_disk_space_reports_raw_and_readable_values(tmp_path):
    def disk_usage(_path):
        return SimpleNamespace(
            total=1_073_741_824,
            used=536_870_912,
            free=536_870_912,
            percent=50.0,
        )

    result = GetDiskSpaceCommand(
        disk_usage_provider=disk_usage,
    ).invoke([str(tmp_path)])

    assert result["success"] is True
    assert result["disk_info"]["path"] == str(tmp_path)
    assert result["disk_info"]["total_bytes"] == 1_073_741_824
    assert result["disk_info"]["used_bytes"] == 536_870_912
    assert result["disk_info"]["free_bytes"] == 536_870_912
    assert result["disk_info"]["total"] == "1.00 GB"
    assert result["disk_info"]["percent"] == 50.0
    assert result["meta"]["command"] == "getDiskSpace"


def test_get_disk_space_missing_path_is_an_explicit_failure(tmp_path):
    missing = tmp_path / "missing"

    def unexpected_disk_probe(_path):
        raise AssertionError("A missing path must fail before probing psutil.")

    result = GetDiskSpaceCommand(
        disk_usage_provider=unexpected_disk_probe,
    ).invoke([str(missing)])

    assert result["success"] is False
    assert result["error"] == f"Path '{missing}' does not exist"
    assert "does not exist" in result["message"]
    assert result["meta"]["schema_version"] == 1
