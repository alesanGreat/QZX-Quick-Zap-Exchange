#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Find files by name and metadata with one structured result contract."""

from qzx.core.command_base import CommandBase
from qzx.core.recursive_findfiles_utils import find_files
from qzx.core.storage_validation import StorageInputError, storage_directory
from ._file_search_parameters import (
    SearchParameterError, parse_boolean, parse_date_limit, parse_limit,
    parse_patterns, parse_recursion, parse_size_limit, search_options,
)
from ._file_search_scan import collect_files, file_depth


class FindFilesCommand(CommandBase):
    """Search for files without mixing in directory listings or content grep."""

    name = "findFiles"
    description = (
        "Finds files by name, depth, size, and modification date with "
        "structured metadata"
    )
    category = "file"
    _byte_units = ("B", "KiB", "MiB", "GiB", "TiB", "PiB")

    parameters = [
        {
            "name": "search_path",
            "description": "Directory where the search starts",
            "required": False,
            "default": ".",
        },
        {
            "name": "pattern",
            "description": "File name glob such as *.txt or data-???.csv; defaults to all files",
            "required": False,
            "default": "*",
        },
        {
            "name": "recursive",
            "description": "Search depth: -r for unlimited, false for this directory only, or -rN for N levels",
            "required": False,
            "default": "-r",
        },
        {
            "name": "min_size",
            "description": "Minimum size, for example 500KB, 10MiB, or bytes",
            "required": False,
            "default": None,
        },
        {
            "name": "max_size",
            "description": "Maximum size, for example 2GB, 20MiB, or bytes",
            "required": False,
            "default": None,
        },
        {
            "name": "modified_after",
            "description": 'Only files modified at or after YYYY-MM-DD, "today", or "yesterday"',
            "required": False,
            "default": None,
        },
        {
            "name": "modified_before",
            "description": 'Only files modified before YYYY-MM-DD, "today", or "yesterday"',
            "required": False,
            "default": None,
        },
        {
            "name": "exclude",
            "description": "Comma-separated file-name globs to exclude",
            "required": False,
            "default": None,
        },
        {
            "name": "exclude_dirs",
            "description": "Comma-separated directory-name globs to skip",
            "required": False,
            "default": None,
        },
        {
            "name": "sort_by",
            "description": "Sort by path, name, size, or modified",
            "required": False,
            "default": "path",
        },
        {
            "name": "descending",
            "description": "Reverse the selected sort order (true/false)",
            "required": False,
            "default": False,
        },
        {
            "name": "limit",
            "description": "Maximum number of files returned after sorting",
            "required": False,
            "default": None,
        },
    ]

    examples = [
        {
            "command": 'qzx findFiles . "*.py" --exclude-dirs ".git,.venv"',
            "description": "Find Python files recursively while skipping common metadata directories",
        },
        {
            "command": 'qzx findFiles Downloads "*" --min-size 100MiB --sort-by size --descending true --limit 20',
            "description": "Return the 20 largest matching files of at least 100 MiB",
        },
        {
            "command": 'qzx findFiles logs "*.log" --modified-after 2026-07-01 --recursive false',
            "description": "Find recently modified log files in one directory",
        },
    ]

    def __init__(self, *, finder=find_files):
        """Expose the filesystem enumeration boundary for deterministic evidence."""
        self._finder = finder

    def execute(self, search_path=".", pattern="*", recursive="-r", min_size=None,
                max_size=None, modified_after=None, modified_before=None,
                exclude=None, exclude_dirs=None, sort_by="path", descending=False, limit=None):
        """Stream metadata, retain only the requested view, and expose coverage gaps."""
        try:
            root = storage_directory(search_path or ".")
        except StorageInputError as exc:
            code = "invalid_search_path" if exc.code == "invalid_path" else exc.code
            return self._failure(code, str(exc), search_path=search_path)
        if not isinstance(pattern, str) or not pattern.strip():
            return self._failure(
                "invalid_pattern", "Pattern must be a non-empty file-name glob.", search_path=root,
            )
        try:
            options = search_options(
                recursive, min_size, max_size, modified_after, modified_before,
                exclude, exclude_dirs, sort_by, descending, limit,
            )
        except SearchParameterError as exc:
            return self._failure(exc.code, str(exc), search_path=root, pattern=pattern)
        except ValueError as exc:
            return self._failure("invalid_parameter", str(exc), search_path=root, pattern=pattern)
        try:
            scan, results = collect_files(
                root, pattern, options, self._finder, self._format_bytes
            )
        except OSError as exc:
            return self._failure(
                "search_failed", f"File search could not be completed: {exc}",
                search_path=root, pattern=pattern,
            )
        return self._success_result(root, pattern, options, scan, results)

    def _success_result(self, root, pattern, options, scan, results):
        returned_size = sum(item["size_bytes"] for item in results)
        recursion_label = "unlimited" if options.depth is None else "none" if options.depth == 0 else options.depth
        return {
            "success": True,
            "message": self._message(root, pattern, scan, results, returned_size),
            "search_path": root, "pattern": pattern, "recursive": recursion_label,
            "filters": {
                "min_size_bytes": options.min_bytes, "max_size_bytes": options.max_bytes,
                "modified_after": options.modified_after, "modified_before": options.modified_before,
                "exclude": options.exclude, "exclude_dirs": options.exclude_dirs,
            },
            "sort": {"by": options.sort_by, "descending": options.descending},
            "matched_count": scan.matched_count,
            "matched_size_bytes": scan.matched_size_bytes,
            "matched_size_readable": self._format_bytes(scan.matched_size_bytes),
            "count": len(results), "total_size_bytes": returned_size,
            "total_size_readable": self._format_bytes(returned_size),
            "limit": options.limit, "truncated": len(results) < scan.matched_count,
            "partial": scan.partial, "scan_complete": not scan.partial,
            "skipped_unreadable": scan.skipped_unreadable,
            "skipped_search_paths": scan.skipped_search_paths,
            "skipped_special_files": scan.skipped_special_files,
            "warnings": scan.warnings(), "results": results,
        }

    def _message(self, root, pattern, scan, results, returned_size):
        if scan.matched_count:
            message = (
                f"Found {scan.matched_count} matching file{'s' if scan.matched_count != 1 else ''} "
                f"in '{root}'. Returning {len(results)} file{'s' if len(results) != 1 else ''} "
                f"totaling {self._format_bytes(returned_size)}."
            )
        else:
            message = f"No readable files matched '{pattern}' in '{root}'."
        if scan.partial:
            message += " The search is partial; inspect warnings before drawing conclusions."
        return message

    @staticmethod
    def _failure(error_code, message, **details):
        return {
            "success": False, "message": message, "error": message,
            "error_code": error_code, "details": details,
        }

    _parse_recursion = staticmethod(parse_recursion)
    _parse_size_limit = staticmethod(parse_size_limit)
    _parse_date_limit = staticmethod(parse_date_limit)
    _parse_patterns = staticmethod(parse_patterns)
    _parse_boolean_parameter = staticmethod(parse_boolean)
    _parse_limit = staticmethod(parse_limit)
    _file_depth = staticmethod(file_depth)
