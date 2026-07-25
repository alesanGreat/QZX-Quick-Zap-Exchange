#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Real-environment tests for the current-user command."""

import getpass
import os

import psutil

from qzx.commands.system.get_current_user import GetCurrentUserCommand


def test_format_bytes():
    command = GetCurrentUserCommand()
    assert command._format_bytes(500) == "500.00 B"
    assert command._format_bytes(1024) == "1.00 KB"
    assert command._format_bytes(1024 * 1024) == "1.00 MB"
    assert command._format_bytes(1024 * 1024 * 1024) == "1.00 GB"


def test_execute_reports_the_real_user_process_and_working_directory():
    result = GetCurrentUserCommand().execute()

    assert result["success"] is True
    assert result["username"] == getpass.getuser()
    assert result["home_directory"] == os.path.expanduser("~")
    assert result["current_directory"] == os.getcwd()
    assert result["user_id"] == psutil.Process().username()
    assert result["processes"]["count"] >= 1
    assert result["processes"]["total_memory_usage"] > 0
    assert result["processes"]["total_memory_usage_readable"]
    assert f"Current user: {getpass.getuser()}" in result["message"]
