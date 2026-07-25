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
    assert isinstance(result["errors"], list)
    for item in result["startup_programs"]:
        assert item["name"]
        assert item["command"]
        assert item["source"]
        assert item["type"] in {"registry", "directory", "desktop_file"}


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
