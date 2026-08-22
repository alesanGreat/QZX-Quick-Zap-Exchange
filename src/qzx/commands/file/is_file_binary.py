#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Classify bounded, distributed file content as binary or text."""

from __future__ import annotations

from qzx.core.command_base import CommandBase
from qzx.core.file_content_analysis import (
    FileChangedDuringReadError,
    DEFAULT_BINARY_SAMPLE_SIZE,
    MAX_SAMPLE_SIZE,
    MIN_SAMPLE_SIZE,
    analyze_binary_content,
    detect_builtin_type,
    normalize_binary_threshold,
    normalize_boolean,
    normalize_sample_size,
    read_distributed_sample,
    validate_regular_file,
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
        sample_budget, error = normalize_sample_size(
            sample_size,
            default=DEFAULT_BINARY_SAMPLE_SIZE,
        )
        if error is not None:
            return error
        threshold, error = normalize_binary_threshold(binary_threshold)
        if error is not None:
            return error
        follow_links, error = normalize_boolean(
            follow_symlinks,
            field="follow_symlinks",
            command_base=self,
        )
        if error is not None:
            return error

        target, error = validate_regular_file(
            file_path,
            follow_symlinks=follow_links,
        )
        if error is not None:
            return error
        try:
            sample = read_distributed_sample(
                target,
                sample_budget,
                **(
                    {"open_file": self._open_file}
                    if self._open_file is not None
                    else {}
                ),
            )
        except FileChangedDuringReadError as exc:
            return {
                "success": False,
                "error_code": "file_changed_during_read",
                "error": f"{type(exc).__name__}: {exc}",
                "message": (
                    "The file changed while QZX was reading its bounded sample, "
                    "so no classification was published."
                ),
                "details": target.evidence(),
            }
        except OSError as exc:
            return {
                "success": False,
                "error_code": "file_read_failed",
                "error": f"{type(exc).__name__}: {exc}",
                "message": "QZX could not read the requested file sample.",
                "details": target.evidence(),
            }

        analysis = analyze_binary_content(
            sample,
            threshold=threshold,
            path=target.analyzed_path,
            detect_encoding=self._detect_encoding,
        )
        detected_type = detect_builtin_type(
            target.analyzed_path,
            sample,
            analysis,
        )
        kind = "binary" if analysis["is_binary"] else "text"
        return {
            "success": True,
            "message": (
                f"File '{target.absolute_path}' is classified as {kind}; "
                f"{sample.analyzed_bytes} of {target.file_size} bytes were "
                f"analyzed using {sample.strategy}."
            ),
            "file_path": str(target.absolute_path),
            "analyzed_path": str(target.analyzed_path),
            "is_binary": analysis["is_binary"],
            "file_size": target.file_size,
            "file_size_readable": self._format_bytes(float(target.file_size)),
            "analyzed_bytes": sample.analyzed_bytes,
            "mime_type": detected_type.mime_type,
            "details": {
                "target": target.evidence(),
                "sampling": sample.evidence(),
                "binary_analysis": analysis,
                "detected_type": detected_type.evidence(),
            },
        }
