#!/usr/bin/env python

"""Compare two bounded files as exact bytes or decoded text."""

from typing import ClassVar

from qzx.commands.development._file_comparison_support import (
    COMPARE_RESULT_SCHEMA,
    compare_binary,
    compare_full,
    compare_percent,
    compare_summary,
    comparison_error,
    decode_text,
    execute_file_comparison,
    file_too_large,
    looks_binary,
    normalize_max_bytes,
    sha256,
)
from qzx.core.command_base import CommandBase


class CompareFilesCommand(CommandBase):
    """Compare text line-by-line and binary files by exact bytes and SHA-256."""

    name = "compareFiles"
    description = "Compares text files line by line and binary files by exact bytes and SHA-256"
    category = "development"
    DEFAULT_MAX_BYTES = 1_048_576
    parameters: ClassVar[list[dict[str, object]]] = [
        {"name": "file1", "description": "Path to the first file", "required": True},
        {"name": "file2", "description": "Path to the second file", "required": True},
        {"name": "mode", "description": 'Comparison mode: "full", "summary", or "percent"', "required": False, "default": "full"},
        {"name": "max_bytes", "description": "Maximum allowed size of each file in bytes (defaults to 1 MiB)", "required": False, "default": DEFAULT_MAX_BYTES},
    ]
    examples: ClassVar[list[dict[str, str]]] = [
        {"command": 'qzx compareFiles "file1.py" "file2.py"', "description": "Compare two Python files and show every difference"},
        {"command": 'qzx compareFiles "file1.txt" "file2.txt" "summary"', "description": "Show a summary of differences between two text files"},
        {"command": 'qzx compareFiles "version1.js" "version2.js" "percent"', "description": "Show the similarity percentage between two JavaScript files"},
        {"command": 'qzx compareFiles "image-a.png" "image-b.png"', "description": "Check whether two binary files are exactly equal by bytes and SHA-256"},
    ]
    result_schema: ClassVar[dict[str, object]] = COMPARE_RESULT_SCHEMA

    _error = staticmethod(comparison_error)
    _normalize_max_bytes = staticmethod(normalize_max_bytes)
    _looks_binary = staticmethod(looks_binary)
    _decode_text = classmethod(decode_text)
    _sha256 = staticmethod(sha256)
    _file_too_large = file_too_large
    _compare_binary = compare_binary
    _compare_full = compare_full
    _compare_summary = compare_summary
    _compare_percent = compare_percent

    def execute(self, file1, file2, mode="full", max_bytes=DEFAULT_MAX_BYTES):
        """Return a bounded comparison in the requested mode."""
        return execute_file_comparison(self, file1, file2, mode, max_bytes)
