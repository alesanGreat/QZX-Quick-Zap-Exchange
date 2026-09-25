#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Classify bounded, distributed file content as binary or text."""

from __future__ import annotations

from qzx.core.command_base import CommandBase
from qzx.commands.file._binary_file_workflow import execute_file_binary
from qzx.core.file_content_analysis import (
    DEFAULT_BINARY_SAMPLE_SIZE,
    MAX_SAMPLE_SIZE,
    MIN_SAMPLE_SIZE,
)


class IsFileBinaryCommand(CommandBase):
    """Inspect one regular file with bounded, distributed sampling."""

    name = "isFileBinary"
    description = (
        "Determines whether a regular file is binary or text using bounded "
        "start/middle/end content sampling"
    )
    category = "file"
    _byte_units = ("B", "KB", "MB", "GB", "TB", "PB")

    parameters = [
        {
            "name": "file_path",
            "description": "Path to the regular file to analyze",
            "required": True,
            "type": "str",
        },
        {
            "name": "sample_size",
            "description": (
                f"Total sample budget in bytes ({MIN_SAMPLE_SIZE} through "
                f"{MAX_SAMPLE_SIZE})"
            ),
            "required": False,
            "default": DEFAULT_BINARY_SAMPLE_SIZE,
            "type": "int",
        },
        {
            "name": "binary_threshold",
            "description": (
                "Suspicious-control-byte percentage greater than 0 and at most "
                "100, used when no definitive content signature exists"
            ),
            "required": False,
            "default": 10.0,
            "type": "float",
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
            "command": "qzx isFileBinary script.py",
            "description": "Classify a source file with the default distributed sample",
        },
        {
            "command": "qzx isFileBinary image.jpg 4096 5",
            "description": "Use a 4 KiB sample budget and a 5 percent threshold",
        },
        {
            "command": "qzx isFileBinary reviewed-link --follow_symlinks",
            "description": "Analyze the resolved target of an explicitly reviewed link",
        },
    ]

    def __init__(self, *, open_file=None, detect_encoding=None):
        super().__init__()
        self._open_file = open_file
        self._detect_encoding = detect_encoding

    def execute(
        self,
        file_path,
        sample_size=DEFAULT_BINARY_SAMPLE_SIZE,
        binary_threshold=10.0,
        follow_symlinks=False,
    ):
        """Inspect one regular file with bounded, distributed sampling."""
        return execute_file_binary(
            self,
            file_path,
            sample_size,
            binary_threshold,
            follow_symlinks,
        )
