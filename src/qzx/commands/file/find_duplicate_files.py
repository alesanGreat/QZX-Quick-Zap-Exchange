#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Find independent duplicate files with explicit scope and evidence completeness."""

import os

from qzx.core.command_base import CommandBase
from qzx.core.path_operation_utils import file_sha256, files_identical
from qzx.core.storage_validation import (
    StorageInputError, bounded_integer, minimum_file_bytes, storage_directory,
)
from ._duplicate_inventory import (
    EXCLUDED_DIRECTORIES,
    collect_inventory,
    file_snapshot,
)
from ._duplicate_presentation import duplicate_result
from ._duplicate_verification import verified_duplicate_groups


class FindDuplicateFilesCommand(CommandBase):
    """Identify duplicate content without treating hardlink aliases as extra copies."""

    name = "findDuplicateFiles"
    description = "Scans a directory for identical files using size, SHA-256, and byte-for-byte verification"
    category = "file"
    _byte_units = ("B", "KB", "MB", "GB")

    parameters = [
        {
            "name": "scan_path",
            "description": "Path to start searching for duplicate files (defaults to current directory)",
            "required": False,
            "default": ".",
        },
        {
            "name": "min_size_kb",
            "description": "Minimum file size in KB to consider for duplicates (defaults to 10)",
            "required": False,
            "default": "10",
        },
        {
            "name": "max_depth",
            "description": "Maximum depth level to walk directories recursively (defaults to 4)",
            "required": False,
            "default": "4",
        },
    ]

    examples = [
        {
            "command": "qzx findDuplicateFiles",
            "description": "Search for duplicates in the current directory (min 10KB)",
        },
        {
            "command": "qzx findDuplicateFiles C:/my-assets 0",
            "description": "Search for all duplicate files of any size inside C:/my-assets",
        },
    ]

    def __init__(
        self,
        *,
        hash_reader=file_sha256,
        compare_reader=files_identical,
        walk_factory=os.walk,
        snapshot_reader=file_snapshot,
    ):
        """Expose deterministic filesystem/content boundaries for tests and embedding."""
        self._hash_reader = hash_reader
        self._compare_reader = compare_reader
        self._walk_factory = walk_factory
        self._snapshot_reader = snapshot_reader

    def execute(self, scan_path=".", min_size_kb="10", max_depth="4"):
        """Scan depth 0..64 inclusively; return useful partial evidence explicitly."""
        try:
            root = storage_directory(scan_path)
            minimum = minimum_file_bytes(min_size_kb)
            depth = bounded_integer(max_depth, "max_depth", 0, 64)
        except StorageInputError as exc:
            return self._failure(exc.code, str(exc))
        except ValueError as exc:
            return self._failure("invalid_parameter", str(exc))
        inventory = collect_inventory(
            root,
            minimum,
            depth,
            walk_factory=self._walk_factory,
            snapshot_reader=self._snapshot_reader,
        )
        if not inventory.statistics["directories_scanned"]:
            return self._failure("directory_unreadable", f"Cannot scan directory '{root}'.")
        duplicates = verified_duplicate_groups(
            inventory,
            self._get_sha256,
            self._files_identical,
            self._format_bytes,
            snapshot_reader=self._snapshot_reader,
        )
        return duplicate_result(
            inventory,
            duplicates,
            self._format_bytes,
            depth=depth,
            minimum=minimum,
            excluded=EXCLUDED_DIRECTORIES,
        )

    @staticmethod
    def _failure(code, message):
        return {"success": False, "error_code": code, "error": message, "message": message}

    def _get_sha256(self, filepath):
        """I/O failures are recorded by the verification layer, never silenced."""
        return self._hash_reader(filepath)

    def _files_identical(self, first_path, second_path):
        """A digest match is only a candidate, not proof of equal bytes."""
        return self._compare_reader(first_path, second_path)
