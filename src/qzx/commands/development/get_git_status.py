#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""GetGitStatus Command - structured repository status and recent history."""

from qzx.commands.development._git_status_support import execute_git_status, run_git
from qzx.core.command_base import CommandBase


class GetGitStatusCommand(CommandBase):
    """Retrieve comprehensive, structured Git repository information."""

    name = "getGitStatus"
    description = "Provides a structured summary of the Git repository state (branch, remote, changes, recent commits)"
    category = "development"
    parameters = [
        {
            "name": "repo_path",
            "description": "Path to the directory to scan (defaults to the current working directory)",
            "required": False,
            "default": ".",
        }
    ]
    examples = [
        {
            "command": "qzx getGitStatus",
            "description": "Show git status for the current directory",
        },
        {
            "command": "qzx getGitStatus C:/some/path",
            "description": "Show git status for the repository at C:/some/path",
        },
    ]

    _run_git = run_git

    def execute(self, repo_path="."):
        """Retrieve Git details for ``repo_path`` without mutating it."""
        return execute_git_status(self, repo_path)
