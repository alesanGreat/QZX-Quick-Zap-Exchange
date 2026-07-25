#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests that inspect real executable resolution and process output."""

import os
from pathlib import Path
import sys

from qzx.commands.system.check_dependency import CheckDependencyCommand


def test_empty_dependency_name():
    result = CheckDependencyCommand().execute("")
    assert result["success"] is False
    assert "cannot be empty" in result["error"]


def test_real_missing_dependency():
    dependency = "qzx-tool-that-does-not-exist-8f3d7483"
    result = CheckDependencyCommand().execute(dependency)

    assert result["success"] is True
    assert result["dependency"] == dependency
    assert result["installed"] is False
    assert "is not installed" in result["message"]


def test_real_python_dependency_and_version():
    result = CheckDependencyCommand().execute(sys.executable)

    assert result["success"] is True
    assert result["installed"] is True
    assert Path(result["executable_path"]).resolve() == Path(
        os.path.abspath(sys.executable)
    ).resolve()
    assert result["version"]
    assert result["version"].lstrip("v").startswith("3.13")
