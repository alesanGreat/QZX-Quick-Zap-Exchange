#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Read text faithfully in bounded pages for people, scripts and AI agents."""

from qzx.core.command_base import CommandBase
from ._read_file_page import read_error_result, read_file_page
from ._read_file_text import DEFAULT_READ_BYTES, normalize_options


class ReadFileCommand(CommandBase):
    """Read one regular file without silently replacing undecodable bytes."""

    name = "readFile"
    description = "Reads and displays the content of a file"
    category = "file"

    parameters = [
        {
            "name": "file_path",
            "description": "Path to the text file to read",
            "required": True,
            "type": "str",
        },
        {
            "name": "max_lines",
            "description": "Maximum lines per page; omitted means no line limit within max_bytes. Zero reads no content.",
            "required": False,
            "default": None,
            "type": "int",
        },
        {
            "name": "max_bytes",
            "description": "Source bytes per page (1 to 16777216; default 65536), plus a four-byte encoding probe. Split characters remain for the next page.",
            "required": False,
            "default": DEFAULT_READ_BYTES,
            "type": "int",
        },
        {
            "name": "offset",
            "description": "Zero-based source byte offset. Use the exact next_read values to continue without repeating or losing text.",
            "required": False,
            "default": 0,
            "type": "int",
        },
        {
            "name": "encoding",
            "description": "auto detects a Unicode BOM, otherwise requires UTF-8. Explicit UTF-8/16/32, ASCII, Latin-1, CP1252, CP437 and CP850 are supported; decoding is strict.",
            "required": False,
            "default": "auto",
            "type": "str",
        },
        {
            "name": "expected_fingerprint",
            "description": "Optional stat fingerprint token from next_read. Rejects ordinary file changes between pages; this is not a content hash or immutable snapshot.",
            "required": False,
            "default": None,
             "type": "str",
        },
    ]

    examples = [
        {
            "command": "qzx readFile myfile.txt",
            "description": "Read up to 64 KiB of text, preserving Unicode and original line endings",
        },
        {
            "command": "qzx readFile myfile.txt 10 --json",
            "description": "Read the first ten lines within the byte budget and inspect next_read",
        },
        {
            "command": 'qzx readFile "path with spaces/myfile.txt"',
            "description": "Read a file with spaces in the path",
        },
        {
            "command": "qzx readFile application.log --max-bytes 4096 --offset 0 --json",
            "description": "Start a bounded log-reading workflow; continue with the returned next_read values",
        },
        {
            "command": "qzx readFile legacy.txt --encoding cp1252 --json",
            "description": "Read a known Windows-1252 file without replacing accented characters",
        },
    ]

    result_schema = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "message": {"type": "string"},
            "content": {"type": "string"},
            "details": {"type": "object"},
            "error_code": {"type": "string"},
            "error": {"type": "string"},
        },
        "required": ["success", "message"],
    }

    def __init__(self, *, page_reader=read_file_page):
        """Expose the bounded page-I/O boundary for deterministic evidence."""
        self._page_reader = page_reader

    def execute(self, file_path, max_lines=None, max_bytes=DEFAULT_READ_BYTES,
                offset=0, encoding="auto", expected_fingerprint=None):
        """Return one lossless page and explicit continuation metadata."""
        try:
            options = normalize_options(max_lines, max_bytes, offset, encoding, expected_fingerprint)
            return self._page_reader(file_path, options, self._format_bytes)
        except (OSError, ValueError, TypeError, OverflowError) as error:
            return read_error_result(error, file_path)
