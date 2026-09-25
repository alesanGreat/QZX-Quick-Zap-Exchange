#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Count logical Unicode lines with bounded memory and stable file evidence."""

from __future__ import annotations

import codecs

from qzx.commands.file._count_lines_workflow import count_file_lines
from qzx.commands.file._line_count_stream import (
    consume_text,
    count_stream,
    finish_line,
)
from qzx.core.command_base import CommandBase


class CountLinesCommand(CommandBase):
    """Count text lines without loading the complete file into memory."""

    name = "countLines"
    description = (
        "Counts logical Unicode lines in a stable regular file using bounded-memory "
        "streaming and explicit newline evidence"
    )
    category = "file"
    _CHUNK_SIZE = 64 * 1024
    _UNICODE_LINE_BREAKS = {
        "\n": "lf",
        "\v": "vertical_tab",
        "\f": "form_feed",
        "\x1c": "file_separator",
        "\x1d": "group_separator",
        "\x1e": "record_separator",
        "\x85": "next_line",
        "\u2028": "line_separator",
        "\u2029": "paragraph_separator",
    }

    parameters = [
        {
            "name": "file_path",
            "description": "Path to the regular text file to count",
            "required": True,
            "type": "str",
        },
        {
            "name": "encoding",
            "description": (
                "Text encoding name, or 'auto' to use bounded content detection"
            ),
            "required": False,
            "default": "auto",
            "type": "str",
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
            "command": "qzx countLines source.py",
            "description": "Count source lines with automatic encoding detection",
        },
        {
            "command": "qzx countLines legacy.txt windows-1252",
            "description": "Count a file with an explicit legacy encoding",
        },
        {
            "command": "qzx countLines reviewed-link auto true",
            "description": "Count the resolved target of an explicitly reviewed link",
        },
    ]

    def __init__(self, *, open_file=None, detect_encoding=None):
        super().__init__()
        self._open_file = open_file or open
        self._detect_encoding = detect_encoding

    def execute(self, file_path, encoding="auto", follow_symlinks=False):
        return count_file_lines(
            self,
            file_path,
            encoding,
            follow_symlinks,
        )

    @staticmethod
    def _normalize_encoding(value):
        if not isinstance(value, str) or not value.strip():
            return None, {
                "success": False,
                "error_code": "invalid_encoding",
                "error": "encoding must be non-empty text.",
                "message": "Provide 'auto' or a valid Python codec name.",
            }
        normalized = value.strip()
        if normalized.casefold() == "auto":
            return "auto", None
        try:
            return codecs.lookup(normalized).name, None
        except LookupError as exc:
            return None, {
                "success": False,
                "error_code": "invalid_encoding",
                "error": f"{type(exc).__name__}: {exc}",
                "message": f"Encoding '{normalized}' is not available.",
            }

    def _count_stream(self, target, encoding):
        return count_stream(self, target, encoding)

    def _consume_text(self, text, state):
        return consume_text(self, text, state)

    @staticmethod
    def _finish_line(state):
        return finish_line(state)

    @staticmethod
    def _changed_result(target, error, *, phase):
        return {
            "success": False,
            "error_code": "file_changed_during_read",
            "error": f"{type(error).__name__}: {error}",
            "message": (
                "The file changed while QZX was counting lines, so no count was "
                "published."
            ),
            "file_path": str(target.absolute_path),
            "analyzed_path": str(target.analyzed_path),
            "details": {
                "target": target.evidence(),
                "phase": phase,
            },
        }

    @staticmethod
    def _read_failure(target, error, *, phase):
        return {
            "success": False,
            "error_code": "file_read_failed",
            "error": f"{type(error).__name__}: {error}",
            "message": "QZX could not read the requested file while counting lines.",
            "file_path": str(target.absolute_path),
            "analyzed_path": str(target.analyzed_path),
            "details": {
                "target": target.evidence(),
                "phase": phase,
            },
        }
