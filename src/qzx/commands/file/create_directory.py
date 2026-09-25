#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Create directories with exact per-path evidence and safe partial rollback."""

from __future__ import annotations

import os
import stat
from pathlib import Path

from qzx.commands.file._create_directory_workflow import create_directories
from qzx.commands.file._directory_creation import (
    create_one_directory,
    creation_failure,
)
from qzx.core.command_base import CommandBase


class CreateDirectoryCommand(CommandBase):
    """Create one or more real directories without traversing path links."""

    name = "createDirectory"
    description = (
        "Creates one or more real directories with deduplication, conflict "
        "detection, and per-target rollback on failure"
    )
    category = "file"
    MAX_PATHS = 1_000

    parameters = [
        {
            "name": "directory_paths",
            "description": "One or more real directory paths to create",
            "required": True,
            "type": "str",
            "is_variadic": True,
        }
    ]

    examples = [
        {
            "command": 'qzx createDirectory "ProjectFolder"',
            "description": 'Create one directory named "ProjectFolder"',
        },
        {
            "command": (
                'qzx createDirectory "src/components" "src/styles" "src/utils"'
            ),
            "description": (
                "Create several project directories and report every target "
                "independently"
            ),
        },
    ]

    def __init__(self, *, mkdir=None, rmdir=None):
        super().__init__()
        self._mkdir = mkdir or os.mkdir
        self._rmdir = rmdir or os.rmdir

    def execute(self, *directory_paths):
        """Create each unique path while preserving reviewable batch evidence."""
        return create_directories(self, directory_paths)

    @staticmethod
    def _normalize_path(requested_path):
        requested_text = repr(requested_path)
        try:
            raw_path = os.fspath(requested_path)
        except TypeError:
            return None, requested_text, {
                "error_code": "invalid_directory_path",
                "error": "Directory paths must be text or path-like objects.",
            }
        if not isinstance(raw_path, str):
            return None, requested_text, {
                "error_code": "invalid_directory_path",
                "error": "Directory paths must resolve to text, not raw bytes.",
            }
        requested_text = raw_path
        if not raw_path:
            return None, requested_text, {
                "error_code": "invalid_directory_path",
                "error": "Directory paths must not be empty.",
            }
        if "\x00" in raw_path:
            return None, requested_text, {
                "error_code": "invalid_directory_path",
                "error": "Directory paths must not contain NUL bytes.",
            }
        try:
            expanded = os.path.expanduser(raw_path)
            normalized = Path(os.path.abspath(expanded))
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            return None, requested_text, {
                "error_code": "invalid_directory_path",
                "error": f"{type(exc).__name__}: {exc}",
            }
        return normalized, requested_text, None

    def _create_one(self, path, *, requested_text, request_index):
        return create_one_directory(
            self,
            path,
            requested_text=requested_text,
            request_index=request_index,
        )

    def _creation_failure(
        self,
        base,
        target,
        created_paths,
        error_code,
        error,
    ):
        return creation_failure(
            self,
            base,
            target,
            created_paths,
            error_code,
            error,
        )

    @staticmethod
    def _path_components(path):
        parts = path.parts
        if not parts:
            return
        current = Path(path.anchor)
        yield current
        for part in parts[1:]:
            current /= part
            yield current

    @staticmethod
    def _path_type(path):
        if not os.path.lexists(path):
            return "missing"
        is_junction = getattr(os.path, "isjunction", None)
        if os.path.islink(path) or (
            is_junction is not None and is_junction(path)
        ):
            return "link"
        mode = os.lstat(path).st_mode
        if stat.S_ISDIR(mode):
            return "directory"
        if stat.S_ISREG(mode):
            return "file"
        return "special entry"
