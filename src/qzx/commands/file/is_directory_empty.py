#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Inspect directory emptiness with streaming, stable, link-safe evidence."""

from __future__ import annotations

import os
import stat

from qzx.commands.file._directory_empty_workflow import execute_directory_empty
from qzx.core.command_base import CommandBase


class IsDirectoryEmptyCommand(CommandBase):
    """Check one stable real directory without materializing its listing."""

    name = "isDirectoryEmpty"
    description = (
        "Checks stable directory emptiness with streaming counts, explicit "
        "hidden-item policy, and no symbolic-link traversal by default"
    )
    category = "file"

    parameters = [
        {
            "name": "directory_path",
            "description": "Path to the real directory to inspect",
            "required": True,
            "type": "str",
        },
        {
            "name": "include_hidden",
            "description": (
                "Count dot-prefixed and platform-hidden entries when deciding "
                "whether the directory is empty"
            ),
            "required": False,
            "default": False,
            "type": "bool",
        },
        {
            "name": "follow_symlinks",
            "description": (
                "Follow reviewed symbolic-link or junction components to their "
                "resolved directory target"
            ),
            "required": False,
            "default": False,
            "type": "bool",
        },
    ]

    examples = [
        {
            "command": "qzx isDirectoryEmpty /path/to/directory",
            "description": "Check visible emptiness without following links",
        },
        {
            "command": "qzx isDirectoryEmpty /path/to/directory true",
            "description": "Include hidden entries in the emptiness decision",
        },
        {
            "command": "qzx isDirectoryEmpty reviewed-link true true",
            "description": "Inspect an explicitly reviewed linked directory target",
        },
    ]

    def __init__(self, *, scandir=None, hidden_predicate=None):
        super().__init__()
        self._scandir = scandir or os.scandir
        self._hidden_predicate = hidden_predicate or self._is_hidden_entry

    def execute(
        self,
        directory_path,
        include_hidden=False,
        follow_symlinks=False,
    ):
        """Return exact counts only when the directory remains stable."""
        return execute_directory_empty(
            self,
            directory_path,
            include_hidden,
            follow_symlinks,
        )

    @staticmethod
    def _empty_counts():
        return {
            "total_entries": 0,
            "considered_entries": 0,
            "ignored_hidden_entries": 0,
            "file_count": 0,
            "directory_count": 0,
            "symlink_count": 0,
            "other_count": 0,
            "unavailable_count": 0,
            "scan_error_count": 0,
        }

    @staticmethod
    def _is_hidden_entry(entry):
        if entry.name.startswith("."):
            return True
        entry_stat = entry.stat(follow_symlinks=False)
        hidden_flag = getattr(stat, "FILE_ATTRIBUTE_HIDDEN", 0x2)
        file_attributes = getattr(entry_stat, "st_file_attributes", 0)
        return bool(file_attributes & hidden_flag)

    @staticmethod
    def _entry_type(entry):
        is_junction = getattr(os.path, "isjunction", None)
        if entry.is_symlink() or (
            is_junction is not None and is_junction(entry.path)
        ):
            return "symlink"
        if entry.is_file(follow_symlinks=False):
            return "file"
        if entry.is_dir(follow_symlinks=False):
            return "directory"
        return "other"

    @staticmethod
    def _record_scan_error(
        counts,
        error_samples,
        path,
        phase,
        error,
    ):
        counts["scan_error_count"] += 1
        if len(error_samples) < 20:
            error_samples.append(
                {
                    "path": str(path),
                    "phase": phase,
                    "error_type": type(error).__name__,
                    "error": str(error),
                }
            )

    @staticmethod
    def _changed_failure(target, counts, error_samples, error):
        details = {
            "target": target.evidence(),
            **counts,
            "scan_complete": False,
            "directory_stable_during_scan": False,
            "symbolic_links_followed_inside_directory": False,
        }
        if error_samples:
            details["scan_error_samples"] = error_samples
        return {
            "success": False,
            "error_code": "directory_changed_during_scan",
            "error": f"{type(error).__name__}: {error}",
            "message": (
                f"Directory '{target.absolute_path}' changed during enumeration, "
                "so QZX did not publish an emptiness conclusion."
            ),
            "directory_path": str(target.absolute_path),
            "analyzed_path": str(target.analyzed_path),
            "details": details,
        }
