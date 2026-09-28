#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Real-filesystem tests for startup-program discovery."""

import platform

from qzx.commands.system import _startup_program_inventory
from qzx.commands.system.list_startup_programs import ListStartupProgramsCommand


def test_execute_reads_the_real_platform_startup_sources():
    result = ListStartupProgramsCommand().execute()

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
    assert result["analysis_complete"] is (not result["errors"])
    assert result["diagnostics_degraded"] is bool(result["errors"])
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


def test_windows_startup_folder_ignores_shell_metadata(tmp_path):
    startup = tmp_path / "Startup"
    startup.mkdir()
    (startup / "desktop.ini").write_text(
        "[.ShellClassInfo]\n",
        encoding="utf-8",
    )
    (startup / "Launch QZX.lnk").write_text(
        "synthetic shortcut",
        encoding="utf-8",
    )

    items, errors = [], []
    _startup_program_inventory._windows_folders(
        ListStartupProgramsCommand(),
        items,
        errors,
        folders=[(str(startup), "Test Startup Folder")],
    )

    assert errors == []
    assert [item["name"] for item in items] == ["Launch QZX.lnk"]


def test_desktop_entry_parser_reads_a_real_file(tmp_path):
    desktop_file = tmp_path / "qzx-test.desktop"
    desktop_file.write_text(
        "[Desktop Entry]\nName=QZX Test App\nExec=qzx version\n",
        encoding="utf-8",
    )

    name, command = ListStartupProgramsCommand()._parse_desktop_file(
        desktop_file
    )

    assert name == "QZX Test App"
    assert command == "qzx version"


def test_unreadable_desktop_entry_is_reported_without_hiding_other_entries(
    tmp_path,
):
    autostart = tmp_path / "autostart"
    autostart.mkdir()
    unreadable = autostart / "broken.desktop"
    unreadable.write_text("[Desktop Entry]\nName=Broken\n", encoding="utf-8")
    valid = autostart / "valid.desktop"
    valid.write_text(
        "[Desktop Entry]\nName=Valid\nExec=qzx version\n",
        encoding="utf-8",
    )

    class SelectiveParserCommand(ListStartupProgramsCommand):
        def _parse_desktop_file(self, filepath):
            if str(filepath) == str(unreadable):
                raise PermissionError("synthetic access denied")
            return super()._parse_desktop_file(filepath)

    items, errors = [], []
    _startup_program_inventory._unix_items(
        SelectiveParserCommand(),
        items,
        errors,
        paths=[(str(autostart), "Test Autostart")],
    )

    assert [item["name"] for item in items] == ["Valid"]
    assert len(errors) == 1
    assert str(unreadable) in errors[0]
    assert "PermissionError: synthetic access denied" in errors[0]


def test_desktop_entry_without_exec_is_reported_not_invented(tmp_path):
    desktop_file = tmp_path / "qzx-incomplete.desktop"
    desktop_file.write_text(
        "[Desktop Entry]\nName=QZX Incomplete App\n",
        encoding="utf-8",
    )

    name, command = ListStartupProgramsCommand()._parse_desktop_file(
        desktop_file
    )
    item = ListStartupProgramsCommand()._startup_item(
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
