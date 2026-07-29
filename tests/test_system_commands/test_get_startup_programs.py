#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Real-filesystem tests for startup-program discovery."""

import platform

from qzx.commands.system.get_startup_programs import GetStartupProgramsCommand


def test_execute_reads_the_real_platform_startup_sources():
    result = GetStartupProgramsCommand().execute()

    assert result["success"] is True
    assert result["os"] == platform.system()
    assert result["total_startup_programs"] == len(result["startup_programs"])
    assert result["actionable_startup_programs"] == sum(
        item["actionable"]
        for item in result["startup_programs"]
    )
    assert result["entries_with_issues"] == sum(
        bool(item["issues"])
        for item in result["startup_programs"]
    )
    assert isinstance(result["errors"], list)
    for item in result["startup_programs"]:
        assert item["name"]
        assert item["source"]
        assert item["type"] in {"registry", "directory", "desktop_file"}
        assert item["actionable"] is bool(item["command"])
        if item["command"]:
            assert item["issues"] == []
        else:
            assert item["actionable"] is False
            assert any("empty command" in issue for issue in item["issues"])


def test_desktop_entry_parser_reads_a_real_file(tmp_path):
    desktop_file = tmp_path / "qzx-test.desktop"
    desktop_file.write_text(
        "[Desktop Entry]\nName=QZX Test App\nExec=qzx version\n",
        encoding="utf-8",
    )

    name, command = GetStartupProgramsCommand()._parse_desktop_file(
        desktop_file
    )

    assert name == "QZX Test App"
    assert command == "qzx version"


def test_desktop_entry_without_exec_is_reported_not_invented(tmp_path):
    desktop_file = tmp_path / "qzx-incomplete.desktop"
    desktop_file.write_text(
        "[Desktop Entry]\nName=QZX Incomplete App\n",
        encoding="utf-8",
    )

    name, command = GetStartupProgramsCommand()._parse_desktop_file(
        desktop_file
    )
    item = GetStartupProgramsCommand()._startup_item(
        name=name,
        command=command,
        source="Test Autostart",
        item_type="desktop_file",
        source_path=desktop_file,
    )

    assert item["name"] == "QZX Incomplete App"
    assert item["command"] == ""
    assert item["actionable"] is False
    assert any("empty command" in issue for issue in item["issues"])
    assert item["source_path"] == str(desktop_file)
