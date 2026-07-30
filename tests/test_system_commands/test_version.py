#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Real-environment tests for the QZX version command."""

import platform

from qzx import __version__
from qzx.commands.system.version import VersionCommand
from qzx.core.command_loader import CommandLoader


def test_execute_reports_the_real_runtime_and_command_catalog():
    result = VersionCommand().execute()

    assert result["success"] is True
    assert result["version"] == __version__
    assert result["system_info"] == {
        "os": platform.system(),
        "os_version": platform.version(),
        "os_release": platform.release(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
    }
    commands = CommandLoader().discover_commands()
    assert result["qzx_info"]["command_count"] == len(set(commands.values()))
    assert f"running on {platform.system()}" in result["message"]
