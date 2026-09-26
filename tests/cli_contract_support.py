#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Shared fixtures for CLI contract regression tests."""

import os
import subprocess
import sys
from pathlib import Path

from qzx.core.command_base import CommandBase

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class DangerousFixtureCommand(CommandBase):
    name = "dangerousFixture"
    maturity = "alpha"
    description = "Test-only high-risk command"
    requires_explicit_approval = True
    backup_target_parameter = "target"
    parameters = [
        {
            "name": "target",
            "description": "Test backup target",
            "required": True,
            "type": "str",
        },
    ]
    examples = []

    def __init__(self):
        self.executions = 0

    def execute(self, target):
        self.executions += 1
        return {"success": True, "message": "executed"}


class RichFixtureCommand(CommandBase):
    name = "richFixture"
    maturity = "alpha"
    description = "Test-only rich command"
    parameters = []
    examples = []

    def execute(self):
        return {
            "success": True,
            "message": "Fixture inspection completed.",
            "details": {
                "items_found": 2,
                "ready": True,
            },
        }


def _run_cli(*arguments, environment_overrides=None, text=True):
    environment = os.environ.copy()
    environment["QZX_TELEMETRY"] = "0"
    environment["PYTHONPATH"] = str(REPOSITORY_ROOT / "src")
    environment.update(environment_overrides or {})
    return subprocess.run(
        [sys.executable, "-m", "qzx", *arguments],
        cwd=REPOSITORY_ROOT,
        env=environment,
        text=text,
        encoding="utf-8" if text else None,
        errors="strict" if text else None,
        capture_output=True,
        timeout=30,
        check=False,
    )
