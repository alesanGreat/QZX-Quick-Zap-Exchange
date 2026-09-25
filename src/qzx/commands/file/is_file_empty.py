#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Inspect zero-byte and whitespace-only file emptiness with bounded memory."""

from __future__ import annotations

import os

from qzx.commands.file._file_empty_workflow import inspect_file_emptiness
from qzx.commands.file._unicode_whitespace_scan import scan_unicode_whitespace
from qzx.core.command_base import CommandBase


class IsFileEmptyCommand(CommandBase):
    """Check one regular file without loading its complete content into memory."""

    name = "isFileEmpty"
    description = (
        "Checks zero-byte or whitespace-only file emptiness with streaming text "
        "decoding and no symbolic-link traversal by default"
    )
    category = "file"
    _byte_units = ("B", "KB", "MB", "GB", "TB", "PB")
    _STREAM_CHUNK_SIZE = 64 * 1024

    parameters = [
        {
            "name": "file_path",
            "description": "Path to the regular file to inspect",
            "required": True,
            "type": "str",
        },
        {
            "name": "consider_whitespace",
            "description": (
                "Treat a fully decoded file containing only Unicode whitespace "
                "as empty"
            ),
            "required": False,
            "default": False,
            "type": "bool",
        },
        {
            "name": "follow_symlinks",
            "description": (
                "Follow reviewed symbolic-link or junction components to their "
                "resolved regular-file target"
            ),
            "required": False,
            "default": False,
            "type": "bool",
        },
    ]

    examples = [
        {
            "command": "qzx isFileEmpty /path/to/file.txt",
            "description": "Check whether a regular file has zero bytes",
        },
        {
            "command": "qzx isFileEmpty /path/to/file.txt true",
            "description": "Also treat Unicode whitespace-only text as empty",
        },
        {
            "command": "qzx isFileEmpty reviewed-link true true",
            "description": "Inspect an explicitly reviewed linked file target",
        },
    ]

    def __init__(self, *, open_file=None, detect_encoding=None):
        super().__init__()
        self._open_file = open_file or open
        self._detect_encoding = detect_encoding

    def execute(
        self,
        file_path,
        consider_whitespace=False,
        follow_symlinks=False,
    ):
        """Return a stable emptiness decision with its exact proof basis."""
        return inspect_file_emptiness(
            self,
            file_path,
            consider_whitespace,
            follow_symlinks,
        )

    def _scan_unicode_whitespace(self, target, encoding):
        return scan_unicode_whitespace(self, target, encoding)

    @staticmethod
    def _first_non_whitespace(text, *, at_text_start):
        for character in text:
            if at_text_start:
                at_text_start = False
                if character == "\ufeff":
                    continue
            if not character.isspace():
                return character, at_text_start
        return None, at_text_start

    @staticmethod
    def _path_fingerprint(path):
        file_stat = os.stat(path, follow_symlinks=True)
        return (
            file_stat.st_size,
            getattr(file_stat, "st_mtime_ns", None),
            file_stat.st_dev,
            file_stat.st_ino,
        )

    @staticmethod
    def _changed_file_result(
        target,
        bytes_scanned,
        reason,
        *,
        phase="whitespace_scan",
    ):
        return {
            "success": False,
            "error_code": "file_changed_during_read",
            "error": reason,
            "message": (
                f"File '{target.absolute_path}' changed while QZX was reading it, "
                "so no emptiness conclusion was published."
            ),
            "file_path": str(target.absolute_path),
            "analyzed_path": str(target.analyzed_path),
            "details": {
                "target": target.evidence(),
                "phase": phase,
                "validated_size": target.file_size,
                "whitespace_scan_bytes": bytes_scanned,
                "full_content_scanned": False,
            },
        }

    @staticmethod
    def _read_failure(target, error, *, phase):
        return {
            "success": False,
            "error_code": "file_read_failed",
            "error": f"{type(error).__name__}: {error}",
            "message": "QZX could not read the requested file.",
            "file_path": str(target.absolute_path),
            "analyzed_path": str(target.analyzed_path),
            "details": {
                "target": target.evidence(),
                "phase": phase,
            },
        }

    def _result(
        self,
        target,
        *,
        consider_whitespace,
        is_empty,
        is_whitespace_only,
        message,
        details,
    ):
        result = {
            "success": True,
            "message": message,
            "file_path": str(target.absolute_path),
            "analyzed_path": str(target.analyzed_path),
            "is_empty": is_empty,
            "file_size": target.file_size,
            "file_size_readable": self._format_bytes(float(target.file_size)),
            "consider_whitespace": consider_whitespace,
            "details": {
                "target": target.evidence(),
                **details,
            },
        }
        if consider_whitespace:
            result["is_whitespace_only"] = is_whitespace_only
        return result
