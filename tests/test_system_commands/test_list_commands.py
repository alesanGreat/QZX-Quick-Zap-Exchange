#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Focused public-contract tests for listCommands."""

from qzx.commands.system.list_commands import ListCommandsCommand


def test_list_commands_reports_the_complete_index_and_maturity():
    result = ListCommandsCommand().invoke([])

    assert result["success"] is True
    assert result["summary"]["commands"] == 87
    assert result["summary"]["categories"] == 4
    assert result["summary"]["filter"] is None
    assert result["maturity_summary"] == {"alpha": 87}
    assert set(result["commands"]) == {
        "development",
        "file",
        "network",
        "system",
    }
    assert result["meta"]["command"] == "listCommands"
    assert result["meta"]["schema_version"] == 1


def test_list_commands_filter_is_case_insensitive_and_preserves_context():
    result = ListCommandsCommand().invoke(["DISK"])

    assert result["success"] is True
    assert result["summary"]["filter"] == "DISK"
    assert result["summary"]["commands"] > 0
    names = {
        command["name"]
        for commands in result["commands"].values()
        for command in commands
    }
    assert "getDiskSpace" in names
    assert all(
        "disk" in command["name"].lower()
        or "disk" in command["description"].lower()
        for commands in result["commands"].values()
        for command in commands
    )
