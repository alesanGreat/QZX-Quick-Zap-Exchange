#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Find files by name and metadata with one structured result contract."""

import datetime
import os
import re

from qzx.core.command_base import CommandBase
from qzx.core.recursive_findfiles_utils import find_files


class FindFilesCommand(CommandBase):
    """Search for files without mixing in directory listings or content grep."""

    name = "findFiles"
    description = (
        "Finds files by name, depth, size, and modification date with "
        "structured metadata"
    )
    category = "file"

    parameters = [
        {
            "name": "search_path",
            "description": "Directory where the search starts",
            "required": False,
            "default": ".",
        },
        {
            "name": "pattern",
            "description": (
                "File name glob such as *.txt or data-???.csv; defaults to all files"
            ),
            "required": False,
            "default": "*",
        },
        {
            "name": "recursive",
            "description": (
                "Search depth: -r for unlimited, false for this directory only, "
                "or -rN for N levels"
            ),
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
            "description": (
                'Only files modified at or after YYYY-MM-DD, "today", or "yesterday"'
            ),
            "required": False,
            "default": None,
        },
        {
            "name": "modified_before",
            "description": (
                'Only files modified before YYYY-MM-DD, "today", or "yesterday"'
            ),
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
            "command": (
                'qzx findFiles Downloads "*" --min-size 100MiB '
                "--sort-by size --descending true --limit 20"
            ),
            "description": "Return the 20 largest matching files of at least 100 MiB",
        },
        {
            "command": (
                'qzx findFiles logs "*.log" --modified-after 2026-07-01 '
                "--recursive false"
            ),
            "description": "Find recently modified log files in one directory",
        },
    ]

    def execute(
        self,
        search_path=".",
        pattern="*",
        recursive="-r",
        min_size=None,
        max_size=None,
        modified_after=None,
        modified_before=None,
        exclude=None,
        exclude_dirs=None,
        sort_by="path",
        descending=False,
        limit=None,
    ):
        """Find files and return complete, consistently structured metadata."""
        try:
            root = os.path.abspath(os.fspath(search_path or "."))
        except TypeError:
            return self._failure(
                "invalid_search_path",
                "Search path must be a filesystem path.",
                search_path=search_path,
            )

        if not os.path.exists(root):
            return self._failure(
                "path_not_found",
                f"Search directory does not exist: {root}",
                search_path=root,
            )
        if not os.path.isdir(root):
            return self._failure(
                "not_a_directory",
                f"Search path is not a directory: {root}",
                search_path=root,
            )
        if not isinstance(pattern, str) or not pattern.strip():
            return self._failure(
                "invalid_pattern",
                "Pattern must be a non-empty file-name glob.",
                search_path=root,
            )

        try:
            recursion_depth = self._parse_recursion(recursive)
            min_size_bytes = self._parse_size_limit(min_size, "min_size")
            max_size_bytes = self._parse_size_limit(max_size, "max_size")
            modified_after_ts = self._parse_date_limit(
                modified_after, "modified_after"
            )
            modified_before_ts = self._parse_date_limit(
                modified_before, "modified_before"
            )
            excluded_files = self._parse_patterns(exclude, "exclude")
            excluded_dirs = self._parse_patterns(exclude_dirs, "exclude_dirs")
            descending_value = self._parse_boolean_parameter(
                descending, "descending"
            )
            limit_value = self._parse_limit(limit)
        except ValueError as exc:
            return self._failure(
                "invalid_parameter",
                str(exc),
                search_path=root,
                pattern=pattern,
            )

        if min_size_bytes is not None and max_size_bytes is not None:
            if min_size_bytes > max_size_bytes:
                return self._failure(
                    "invalid_size_range",
                    "min_size cannot be greater than max_size.",
                    search_path=root,
                    pattern=pattern,
                )
        if modified_after_ts is not None and modified_before_ts is not None:
            if modified_after_ts >= modified_before_ts:
                return self._failure(
                    "invalid_date_range",
                    "modified_after must be earlier than modified_before.",
                    search_path=root,
                    pattern=pattern,
                )

        normalized_sort = str(sort_by).strip().lower()
        sort_keys = {
            "path": lambda item: os.path.normcase(item["path"]),
            "name": lambda item: os.path.normcase(item["name"]),
            "size": lambda item: item["size_bytes"],
            "modified": lambda item: item["modified_timestamp"],
        }
        if normalized_sort not in sort_keys:
            return self._failure(
                "invalid_sort",
                "sort_by must be one of: path, name, size, modified.",
                search_path=root,
                pattern=pattern,
            )

        results = []
        skipped_unreadable = 0
        warning_paths = []
        search_pattern = os.path.join(root, pattern)

        try:
            for file_path in find_files(
                file_path_pattern=search_pattern,
                recursive=recursion_depth,
                exclude_patterns=excluded_files,
                exclude_dirs=excluded_dirs,
                file_type="f",
            ):
                try:
                    file_stat = os.stat(file_path)
                except (FileNotFoundError, OSError):
                    skipped_unreadable += 1
                    if len(warning_paths) < 20:
                        warning_paths.append(os.path.abspath(file_path))
                    continue

                if min_size_bytes is not None and file_stat.st_size < min_size_bytes:
                    continue
                if max_size_bytes is not None and file_stat.st_size > max_size_bytes:
                    continue
                if (
                    modified_after_ts is not None
                    and file_stat.st_mtime < modified_after_ts
                ):
                    continue
                if (
                    modified_before_ts is not None
                    and file_stat.st_mtime >= modified_before_ts
                ):
                    continue

                absolute_path = os.path.abspath(file_path)
                relative_path = os.path.relpath(absolute_path, root)
                results.append(
                    {
                        "name": os.path.basename(absolute_path),
                        "path": absolute_path,
                        "relative_path": relative_path,
                        "depth": self._file_depth(relative_path),
                        "size_bytes": file_stat.st_size,
                        "size_readable": self._format_bytes(file_stat.st_size),
                        "modified_timestamp": file_stat.st_mtime,
                        "modified_at": datetime.datetime.fromtimestamp(
                            file_stat.st_mtime
                        )
                        .astimezone()
                        .isoformat(timespec="seconds"),
                    }
                )
        except OSError as exc:
            return self._failure(
                "search_failed",
                f"File search could not be completed: {exc}",
                search_path=root,
                pattern=pattern,
            )

        results.sort(key=sort_keys[normalized_sort], reverse=descending_value)
        matched_count = len(results)
        matched_size_bytes = sum(item["size_bytes"] for item in results)
        if limit_value is not None:
            results = results[:limit_value]
        returned_size_bytes = sum(item["size_bytes"] for item in results)
        truncated = len(results) < matched_count

        recursion_label = (
            "unlimited"
            if recursion_depth is None
            else "none"
            if recursion_depth == 0
            else recursion_depth
        )
        if matched_count:
            message = (
                f"Found {matched_count} matching file"
                f"{'s' if matched_count != 1 else ''} in '{root}'. "
                f"Returning {len(results)} file"
                f"{'s' if len(results) != 1 else ''} totaling "
                f"{self._format_bytes(returned_size_bytes)}."
            )
        else:
            message = f"No files matched '{pattern}' in '{root}'."

        warnings = []
        if skipped_unreadable:
            warnings.append(
                {
                    "code": "unreadable_files_skipped",
                    "message": (
                        f"Skipped {skipped_unreadable} file"
                        f"{'s' if skipped_unreadable != 1 else ''} that changed "
                        "or could not be read during the search."
                    ),
                    "sample_paths": warning_paths,
                    "sample_truncated": skipped_unreadable > len(warning_paths),
                }
            )

        return {
            "success": True,
            "message": message,
            "search_path": root,
            "pattern": pattern,
            "recursive": recursion_label,
            "filters": {
                "min_size_bytes": min_size_bytes,
                "max_size_bytes": max_size_bytes,
                "modified_after": modified_after,
                "modified_before": modified_before,
                "exclude": excluded_files,
                "exclude_dirs": excluded_dirs,
            },
            "sort": {
                "by": normalized_sort,
                "descending": descending_value,
            },
            "matched_count": matched_count,
            "matched_size_bytes": matched_size_bytes,
            "matched_size_readable": self._format_bytes(matched_size_bytes),
            "count": len(results),
            "total_size_bytes": returned_size_bytes,
            "total_size_readable": self._format_bytes(returned_size_bytes),
            "limit": limit_value,
            "truncated": truncated,
            "skipped_unreadable": skipped_unreadable,
            "warnings": warnings,
            "results": results,
        }

    @staticmethod
    def _failure(error_code, message, **details):
        return {
            "success": False,
            "message": message,
            "error": message,
            "error_code": error_code,
            "details": details,
        }

    @staticmethod
    def _parse_recursion(value):
        if value is None or value is True:
            return None
        if value is False:
            return 0
        if isinstance(value, int):
            if value < 0:
                raise ValueError("recursive depth cannot be negative.")
            return value
        if not isinstance(value, str):
            raise ValueError(
                "recursive must be -r, false, or a non-negative depth such as -r2."
            )

        normalized = value.strip().lower()
        if normalized in {"-r", "--recursive", "true", "yes", "unlimited"}:
            return None
        if normalized in {"false", "no", "none", "0", "off"}:
            return 0
        match = re.fullmatch(r"(?:-r|--recursive)(\d+)", normalized)
        if match:
            return int(match.group(1))
        if normalized.isdigit():
            return int(normalized)
        raise ValueError(
            "recursive must be -r, false, or a non-negative depth such as -r2."
        )

    @staticmethod
    def _parse_size_limit(value, name):
        if value is None or value == "":
            return None
        if isinstance(value, bool):
            raise ValueError(f"{name} must be a non-negative size.")
        if isinstance(value, (int, float)):
            if value < 0:
                raise ValueError(f"{name} cannot be negative.")
            return int(value)
        if not isinstance(value, str):
            raise ValueError(f"{name} must be a number or size such as 10MiB.")

        match = re.fullmatch(
            r"\s*(\d+(?:\.\d+)?)\s*(B|KB|KIB|MB|MIB|GB|GIB|TB|TIB)?\s*",
            value,
            re.IGNORECASE,
        )
        if not match:
            raise ValueError(
                f"{name} must be a non-negative number or size such as 10MiB."
            )
        number = float(match.group(1))
        unit = (match.group(2) or "B").upper()
        multipliers = {
            "B": 1,
            "KB": 1024,
            "KIB": 1024,
            "MB": 1024**2,
            "MIB": 1024**2,
            "GB": 1024**3,
            "GIB": 1024**3,
            "TB": 1024**4,
            "TIB": 1024**4,
        }
        return int(number * multipliers[unit])

    @staticmethod
    def _parse_date_limit(value, name):
        if value is None or value == "":
            return None
        if not isinstance(value, str):
            raise ValueError(f"{name} must use YYYY-MM-DD, today, or yesterday.")
        normalized = value.strip().lower()
        today = datetime.datetime.now().astimezone().replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        if normalized == "today":
            return today.timestamp()
        if normalized == "yesterday":
            return (today - datetime.timedelta(days=1)).timestamp()
        try:
            parsed = datetime.datetime.strptime(normalized, "%Y-%m-%d")
        except ValueError as exc:
            raise ValueError(
                f"{name} must use YYYY-MM-DD, today, or yesterday."
            ) from exc
        return parsed.astimezone().timestamp()

    @staticmethod
    def _parse_patterns(value, name):
        if value is None or value == "":
            return []
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, (list, tuple)) and all(
            isinstance(item, str) for item in value
        ):
            return [item.strip() for item in value if item.strip()]
        raise ValueError(f"{name} must be a comma-separated list of globs.")

    @staticmethod
    def _parse_boolean_parameter(value, name):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "yes", "1", "on"}:
                return True
            if normalized in {"false", "no", "0", "off"}:
                return False
        raise ValueError(f"{name} must be true or false.")

    @staticmethod
    def _parse_limit(value):
        if value is None or value == "":
            return None
        if isinstance(value, bool):
            raise ValueError("limit must be a positive integer.")
        try:
            parsed = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("limit must be a positive integer.") from exc
        if parsed <= 0:
            raise ValueError("limit must be a positive integer.")
        return parsed

    @staticmethod
    def _file_depth(relative_path):
        parent = os.path.dirname(relative_path)
        return 0 if not parent else len(parent.split(os.sep))

    @staticmethod
    def _format_bytes(size_bytes):
        size = float(size_bytes)
        units = ("B", "KiB", "MiB", "GiB", "TiB", "PiB")
        unit_index = 0
        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1
        return f"{size:.2f} {units[unit_index]}"
