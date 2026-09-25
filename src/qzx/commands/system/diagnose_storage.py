#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Diagnose storage pressure without changing or deleting filesystem content."""

from qzx.core.command_base import CommandBase
from qzx.core.storage_validation import StorageInputError, storage_directory
from ._storage_assessment import (
    capacity_assessment, storage_coverage, storage_findings, storage_options,
)
from ._storage_presentation import storage_message, storage_report
from ._storage_recommendations import storage_recommendations


class DiagnoseStorageCommand(CommandBase):
    """Combine capacity, large-file, and duplicate evidence into one workflow."""

    name = "diagnoseStorage"
    description = (
        "Diagnoses storage pressure by combining disk capacity, large-file "
        "discovery, and byte-verified duplicate analysis without deleting anything"
    )
    category = "system"

    parameters = [
        {
            "name": "path",
            "description": "Directory to diagnose (defaults to the current directory)",
            "required": False,
            "default": ".",
        },
        {
            "name": "min_file_size",
            "description": "Minimum size for the large-file view, for example 100MiB or 1GB",
            "required": False,
            "default": "100MiB",
        },
        {
            "name": "max_files",
            "description": "Maximum number of largest files returned (1-1000)",
            "required": False,
            "default": 20,
            "type": "int",
        },
        {
            "name": "duplicate_min_size_kb",
            "description": (
                "Minimum file size in KB considered by the duplicate scan "
                "(defaults to 10240 = 10 MiB)"
            ),
            "required": False,
            "default": 10240,
            "type": "int",
        },
        {
            "name": "max_depth",
            "description": (
                "Maximum directory depth scanned for large and duplicate files "
                "(0-64; defaults to 6)"
            ),
            "required": False,
            "default": 6,
            "type": "int",
        },
        {
            "name": "include_duplicates",
            "description": (
                "Run the byte-verified duplicate scan in the same workflow "
                "(true/false; defaults to true)"
            ),
            "required": False,
            "default": True,
            "type": "bool",
        },
    ]

    examples = [
        {
            "command": "qzx diagnoseStorage",
            "description": "Diagnose storage pressure in the current directory with bounded scans",
        },
        {
            "command": "qzx diagnoseStorage C:/ --max-depth 4 --max-files 30",
            "description": "Inspect a Windows volume with a shallower scan and a larger top-file list",
        },
        {
            "command": (
                "qzx diagnoseStorage /home --include-duplicates false "
                "--min-file-size 500MiB"
            ),
            "description": "Run a faster capacity and large-file diagnosis without hashing duplicates",
        },
    ]

    def __init__(self, *, disk_space_command=None, find_files_command=None,
                 duplicate_files_command=None):
        """Allow deterministic probe injection while keeping normal use self-contained."""
        if disk_space_command is None:
            from qzx.commands.system.get_disk_space import GetDiskSpaceCommand

            disk_space_command = GetDiskSpaceCommand()
        if find_files_command is None:
            from qzx.commands.file.find_files import FindFilesCommand

            find_files_command = FindFilesCommand()
        if duplicate_files_command is None:
            from qzx.commands.file.find_duplicate_files import FindDuplicateFilesCommand

            duplicate_files_command = FindDuplicateFilesCommand()
        self._disk_space = disk_space_command
        self._find_files = find_files_command
        self._find_duplicates = duplicate_files_command

    def execute(self, path=".", min_file_size="100MiB", max_files=20,
                duplicate_min_size_kb=10240, max_depth=6, include_duplicates=True):
        """Run a bounded, read-only diagnosis without upgrading partial evidence."""
        try:
            target = storage_directory(path)
            scope = storage_options(
                min_file_size, max_files, duplicate_min_size_kb, max_depth,
                include_duplicates, self._parse_bool,
            )
        except StorageInputError as exc:
            return self._failure(exc.code, str(exc), path=path)
        except ValueError as exc:
            return self._failure("invalid_parameter", str(exc), path=path)
        capacity = self._disk_space.execute(target)
        if not capacity.get("success"):
            return self._probe_failure("capacity", target, capacity)
        try:
            assessment = capacity_assessment(capacity, self._format_bytes)
        except ValueError as exc:
            return self._failure("invalid_capacity_result", str(exc), path=target)
        large_files, duplicates = self._scan_files(target, scope)
        if not large_files.get("success"):
            return self._probe_failure("large_files", target, large_files)
        return self._success_result(
            target, scope, capacity, large_files, duplicates, assessment
        )

    def _scan_files(self, target, scope):
        large_files = self._find_files.execute(
            search_path=target, pattern="*", recursive=scope["max_depth"],
            min_size=scope["min_file_size"], sort_by="size", descending=True,
            limit=scope["max_files"],
        )
        duplicates = None
        if large_files.get("success") and scope["include_duplicates"]:
            duplicates = self._find_duplicates.execute(
                scan_path=target, min_size_kb=scope["duplicate_min_size_kb"],
                max_depth=scope["max_depth"],
            )
        return large_files, duplicates

    def _success_result(self, target, scope, capacity, large_files, duplicates, assessment):
        assessment.update(storage_findings(large_files, duplicates, self._format_bytes))
        coverage = storage_coverage(capacity, large_files, duplicates)
        return {
            "success": True,
            "message": storage_message(target, assessment, coverage),
            "path": target,
            "partial": coverage["partial"],
            "read_only": True,
            "scan_scope": {
                "max_depth": scope["max_depth"],
                "depth_inclusive": True,
                "large_file_min_size": scope["min_file_size"],
                "max_large_files_returned": scope["max_files"],
                "duplicate_scan_requested": scope["include_duplicates"],
                "duplicate_min_size_kb": scope["duplicate_min_size_kb"],
            },
            "probe_status": coverage["probe_status"],
            "assessment": assessment,
            "capacity": capacity,
            "large_files": large_files,
            "duplicates": duplicates,
            "recommendations": storage_recommendations(assessment, scope, coverage),
            "warnings": coverage["warnings"],
            "related_commands": [
                "getDiskSpace", "findFiles", "findDuplicateFiles", "getDiskHealth",
            ],
            "report": storage_report(
                target, assessment, scope, large_files, duplicates, coverage, self._format_bytes
            ),
        }

    @staticmethod
    def _failure(error_code, message, **details):
        return {
            "success": False, "message": message, "error": message,
            "error_code": error_code, "details": details,
        }

    @classmethod
    def _probe_failure(cls, probe, target, result):
        message = result.get("message") or result.get("error") or "Unknown error"
        return cls._failure(
            f"{probe}_probe_failed",
            f"Storage diagnosis could not complete the {probe} probe: {message}",
            path=target, probe=probe, probe_result=result,
        )
