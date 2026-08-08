#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Focused public-contract tests for help."""

from qzx.commands.system.help import HelpCommand


def test_help_exposes_the_canonical_command_interface():
    result = HelpCommand().invoke(["findFiles"])

    assert result["success"] is True
    assert result["details"]["name"] == "findFiles"
    assert result["details"]["category"] == "file"
    assert result["details"]["maturity"]["stage"] == "alpha"
    assert any(
        parameter["name"] == "search_path"
        for parameter in result["details"]["parameters"]
    )
    assert result["meta"]["command"] == "help"
    assert result["meta"]["schema_version"] == 1


def test_help_unknown_command_fails_with_suggestions_or_discovery_guidance():
    result = HelpCommand().invoke(["findFile"])

    assert result["success"] is False
    assert result["error_code"] == "command_not_found"
    assert "findFiles" in result["message"]
    assert result["details"]["requested"] == "findFile"
    assert "findFiles" in result["details"]["suggestions"]
