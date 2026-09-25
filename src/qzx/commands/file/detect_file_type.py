#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Detect file type with bounded built-in signatures and optional libmagic."""

from __future__ import annotations

from qzx.commands.file._file_type_workflow import execute_file_type
from qzx.core.command_base import CommandBase
from qzx.core.file_content_analysis import (
    DEFAULT_TYPE_SAMPLE_SIZE,
    MAX_SAMPLE_SIZE,
    MIN_SAMPLE_SIZE,
)

try:
    import magic
except ImportError:  # The built-in detector remains fully usable.
    magic = None


_DEFAULT_MAGIC_PROVIDER = object()


class DetectFileTypeCommand(CommandBase):
    """Identify one regular file without trusting its extension alone."""

    name = "detectFileType"
    description = (
        "Identifies a regular file from bounded content signatures with an "
        "optional libmagic refinement and an explicit extension comparison"
    )
    category = "file"
    _byte_units = ("B", "KB", "MB", "GB", "TB", "PB")

    parameters = [
        {
            "name": "file_path",
            "description": "Path to the regular file to identify",
            "required": True,
            "type": "str",
        },
        {
            "name": "detailed_info",
            "description": "Include categories, sample evidence, and detector details",
            "required": False,
            "default": False,
            "type": "bool",
        },
        {
            "name": "sample_size",
            "description": (
                f"Total content sample budget in bytes ({MIN_SAMPLE_SIZE} through "
                f"{MAX_SAMPLE_SIZE})"
            ),
            "required": False,
            "default": DEFAULT_TYPE_SAMPLE_SIZE,
            "type": "int",
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
            "command": "qzx detectFileType image.jpg",
            "description": "Identify a file from its contents rather than its name",
        },
        {
            "command": "qzx detectFileType unknown.bin true",
            "description": "Include detailed detector and sampling evidence",
        },
        {
            "command": "qzx detectFileType reviewed-link false 65536 true",
            "description": "Identify the resolved target of an explicitly reviewed link",
        },
    ]

    def __init__(
        self,
        *,
        magic_provider=_DEFAULT_MAGIC_PROVIDER,
        open_file=None,
        detect_encoding=None,
    ):
        super().__init__()
        self._magic_provider = (
            magic if magic_provider is _DEFAULT_MAGIC_PROVIDER else magic_provider
        )
        self._open_file = open_file
        self._detect_encoding = detect_encoding

    def execute(
        self,
        file_path,
        detailed_info=False,
        sample_size=DEFAULT_TYPE_SAMPLE_SIZE,
        follow_symlinks=False,
    ):
        return execute_file_type(
            self,
            file_path,
            detailed_info=detailed_info,
            sample_size=sample_size,
            follow_symlinks=follow_symlinks,
        )

    def _detect_with_libmagic(self, target, sample):
        provider = self._magic_provider
        if provider is None:
            return None, None, None
        try:
            from_buffer = getattr(provider, "from_buffer", None)
            if callable(from_buffer):
                mime_type = from_buffer(sample.head, mime=True)
                description = from_buffer(sample.head, mime=False)
            else:
                from_file = getattr(provider, "from_file")
                mime_type = from_file(str(target.analyzed_path), mime=True)
                description = from_file(str(target.analyzed_path), mime=False)
            return mime_type, description, None
        except Exception as exc:
            return None, None, f"{type(exc).__name__}: {exc}"
