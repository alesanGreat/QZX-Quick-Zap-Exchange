#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
CurrentDir Command - Shows the current working directory and its contents
"""

import heapq
import os
import shutil
import stat
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from qzx.core.command_base import CommandBase


class CurrentDirCommand(CommandBase):
    """
    Shows the current directory with an immediate inventory by default.

    The default response is intentionally useful to AI agents: besides the
    path, it reports how many files and directories exist at that level,
    without forcing a second listing command. Optional analysis performs one
    recursive scan and reuses it for size, totals, extensions, and notable
    files.

    Symbolic links are counted but never followed, preventing cycles and
    avoiding scans outside the current directory.
    """

    name = "currentDir"
    aliases = ["pwd", "cwd", "dir", "where", "location"]
    description = "Shows the current working directory"
    category = "system"

    parameters = [
        {
            "name": "full",
            "description": "Show the full path (true) or only the directory name (false)",
            "required": False,
            "type": "bool",
            "default": True,
        },
        {
            "name": "size",
            "description": (
                "Recursively calculate logical directory size and descendant "
                "file/directory totals"
            ),
            "required": False,
            "type": "bool",
            "default": False,
        },
        {
            "name": "details",
            "description": (
                "Include a recursive analysis, immediate entry preview, "
                "extension summary, largest/recent files, permissions, and "
                "filesystem capacity"
            ),
            "required": False,
            "type": "bool",
            "default": False,
        },
        {
            "name": "limit",
            "description": (
                "Maximum entries in each details list (1-100, default: 10)"
            ),
            "required": False,
            "type": "int",
            "default": 10,
        },
    ]

    examples = [
        {
            "command": "qzx currentDir",
            "description": (
                "Shows the current path and counts files/directories at that level"
            ),
        },
        {
            "command": "qzx currentDir --size",
            "description": (
                "Adds recursive size and descendant totals in one filesystem scan"
            ),
        },
        {
            "command": "qzx currentDir --details --limit 20",
            "description": (
                "Returns a rich directory analysis with up to 20 items per list"
            ),
        },
        {
            "command": "qzx dir false",
            "description": "Shows only the current directory name as the displayed path",
        },
    ]

    _PROJECT_MARKERS = {
        ".git",
        ".hg",
        ".svn",
        "AGENTS.md",
        "CMakeLists.txt",
        "Cargo.toml",
        "Gemfile",
        "Makefile",
        "README.md",
        "composer.json",
        "deno.json",
        "go.mod",
        "package.json",
        "pom.xml",
        "pyproject.toml",
        "requirements.txt",
        "setup.py",
    }

    @staticmethod
    def _format_bytes(byte_count):
        """Return a stable binary-unit representation of a byte value."""
        size = float(byte_count)
        for unit in ("B", "KiB", "MiB", "GiB", "TiB", "PiB"):
            if abs(size) < 1024 or unit == "PiB":
                precision = 0 if unit == "B" else 2
                return "{:.{}f} {}".format(size, precision, unit)
            size /= 1024

    @staticmethod
    def _counted_noun(count, singular, plural=None):
        """Pair a count with the grammatically correct English noun."""
        return "{} {}".format(
            count,
            singular if count == 1 else (plural or singular + "s"),
        )

    @staticmethod
    def _iso_timestamp(timestamp):
        """Format a filesystem timestamp as timezone-aware UTC ISO 8601."""
        return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()

    @staticmethod
    def _entry_type(entry):
        """Classify a directory entry without following symbolic links."""
        is_junction = getattr(os.path, "isjunction", None)
        if entry.is_symlink() or (is_junction is not None and is_junction(entry.path)):
            return "symlink"
        if entry.is_file(follow_symlinks=False):
            return "file"
        if entry.is_dir(follow_symlinks=False):
            return "directory"
        return "other"

    @staticmethod
    def _is_hidden(entry, entry_stat=None):
        """Recognize portable dotfiles and the Windows hidden-file attribute."""
        if entry.name.startswith("."):
            return True
        if os.name != "nt":
            return False
        try:
            metadata = entry_stat or entry.stat(follow_symlinks=False)
            hidden_flag = getattr(stat, "FILE_ATTRIBUTE_HIDDEN", 0x2)
            attributes = getattr(metadata, "st_file_attributes", 0)
            return bool(attributes & hidden_flag)
        except OSError:
            return False

    @staticmethod
    def _record_scan_error(errors, path, error, limit):
        """Count every scan error while keeping only a bounded sample."""
        errors["count"] += 1
        if len(errors["samples"]) < limit:
            errors["samples"].append(
                {
                    "path": str(path),
                    "error_type": type(error).__name__,
                    "error": str(error),
                }
            )

    def _scan_current_level(self, directory, include_preview, limit):
        """Count and optionally preview entries directly inside ``directory``."""
        counts = Counter()
        immediate_file_size = 0
        names = set()
        preview = []
        errors = {"count": 0, "samples": []}

        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    names.add(entry.name)
                    metadata = None
                    entry_type = None
                    try:
                        entry_type = self._entry_type(entry)
                        counts[entry_type] += 1
                        if self._is_hidden(entry):
                            counts["hidden"] += 1

                        item = {"name": entry.name, "type": entry_type}
                        if entry_type == "file":
                            metadata = entry.stat(follow_symlinks=False)
                            immediate_file_size += metadata.st_size
                            if include_preview:
                                item["size_bytes"] = metadata.st_size
                                item["size_formatted"] = self._format_bytes(
                                    metadata.st_size
                                )

                        if include_preview:
                            if metadata is None:
                                metadata = entry.stat(follow_symlinks=False)
                            item["modified_at"] = self._iso_timestamp(metadata.st_mtime)
                            preview.append(item)
                    except OSError as exc:
                        if entry_type is None:
                            counts["other"] += 1
                        self._record_scan_error(
                            errors,
                            Path(directory) / entry.name,
                            exc,
                            limit,
                        )
        except OSError as exc:
            self._record_scan_error(errors, directory, exc, limit)

        total_entries = sum(
            counts[item_type] for item_type in ("file", "directory", "symlink", "other")
        )
        result = {
            "scope": "current_level",
            "entry_count": total_entries,
            "file_count": counts["file"],
            "directory_count": counts["directory"],
            "symlink_count": counts["symlink"],
            "other_count": counts["other"],
            "hidden_count": counts["hidden"],
            "is_empty": total_entries == 0 and errors["count"] == 0,
            "immediate_files_size_bytes": immediate_file_size,
            "immediate_files_size_formatted": self._format_bytes(immediate_file_size),
            "detected_project_markers": sorted(names & self._PROJECT_MARKERS),
            "scan_complete": errors["count"] == 0,
            "scan_error_count": errors["count"],
        }
        if errors["samples"]:
            result["scan_error_samples"] = errors["samples"]

        if include_preview:
            type_order = {
                "directory": 0,
                "file": 1,
                "symlink": 2,
                "other": 3,
            }
            preview.sort(
                key=lambda item: (
                    type_order[item["type"]],
                    item["name"].casefold(),
                    item["name"],
                )
            )
            result["entry_preview"] = preview[:limit]
            result["entry_preview_count"] = min(len(preview), limit)
            result["entry_preview_truncated"] = len(preview) > limit

        return result

    def _scan_recursive(self, directory, include_details, limit):
        """Perform one bounded-memory recursive analysis of ``directory``."""
        counts = Counter()
        extension_files = Counter()
        extension_sizes = Counter()
        total_size = 0
        largest_files = []
        recent_files = []
        errors = {"count": 0, "samples": []}
        stack = [Path(directory)]

        while stack:
            current = stack.pop()
            try:
                with os.scandir(current) as entries:
                    for entry in entries:
                        entry_path = current / entry.name
                        entry_type = None
                        try:
                            entry_type = self._entry_type(entry)
                            counts[entry_type] += 1
                            if self._is_hidden(entry):
                                counts["hidden"] += 1

                            if entry_type == "directory":
                                stack.append(entry_path)
                                continue
                            if entry_type != "file":
                                continue

                            metadata = entry.stat(follow_symlinks=False)
                            file_size = metadata.st_size
                            total_size += file_size

                            if not include_details:
                                continue

                            extension = Path(entry.name).suffix.lower()
                            extension = extension or "(no extension)"
                            extension_files[extension] += 1
                            extension_sizes[extension] += file_size
                            relative_path = os.path.relpath(entry_path, directory)

                            largest_item = (
                                file_size,
                                relative_path.casefold(),
                                relative_path,
                            )
                            if len(largest_files) < limit:
                                heapq.heappush(largest_files, largest_item)
                            elif largest_item > largest_files[0]:
                                heapq.heapreplace(largest_files, largest_item)

                            recent_item = (
                                metadata.st_mtime,
                                relative_path.casefold(),
                                relative_path,
                                file_size,
                            )
                            if len(recent_files) < limit:
                                heapq.heappush(recent_files, recent_item)
                            elif recent_item > recent_files[0]:
                                heapq.heapreplace(recent_files, recent_item)
                        except OSError as exc:
                            if entry_type is None:
                                counts["other"] += 1
                            self._record_scan_error(
                                errors,
                                entry_path,
                                exc,
                                limit,
                            )
            except OSError as exc:
                self._record_scan_error(errors, current, exc, limit)

        result = {
            "scope": "recursive_descendants",
            "file_count": counts["file"],
            "directory_count": counts["directory"],
            "symlink_count": counts["symlink"],
            "other_count": counts["other"],
            "hidden_count": counts["hidden"],
            "total_size_bytes": total_size,
            "total_size_formatted": self._format_bytes(total_size),
            "size_measurement": (
                "Logical bytes in regular files; directory metadata and "
                "symbolic-link targets are excluded"
            ),
            "symbolic_links_followed": False,
            "scan_complete": errors["count"] == 0,
            "scan_error_count": errors["count"],
        }
        if errors["samples"]:
            result["scan_error_samples"] = errors["samples"]

        if include_details:
            sorted_extensions = sorted(
                extension_files,
                key=lambda extension: (
                    -extension_files[extension],
                    -extension_sizes[extension],
                    extension,
                ),
            )
            selected_extensions = sorted_extensions[:limit]
            omitted_extensions = sorted_extensions[limit:]
            result["extensions"] = [
                {
                    "extension": extension,
                    "file_count": extension_files[extension],
                    "size_bytes": extension_sizes[extension],
                    "size_formatted": self._format_bytes(extension_sizes[extension]),
                }
                for extension in selected_extensions
            ]
            result["extension_group_count"] = len(sorted_extensions)
            result["extensions_truncated"] = bool(omitted_extensions)
            result["omitted_extensions"] = {
                "group_count": len(omitted_extensions),
                "file_count": sum(
                    extension_files[extension] for extension in omitted_extensions
                ),
                "size_bytes": sum(
                    extension_sizes[extension] for extension in omitted_extensions
                ),
            }
            result["largest_files"] = [
                {
                    "relative_path": relative_path,
                    "size_bytes": file_size,
                    "size_formatted": self._format_bytes(file_size),
                }
                for file_size, _normalized_path, relative_path in sorted(
                    largest_files,
                    reverse=True,
                )
            ]
            result["recently_modified_files"] = [
                {
                    "relative_path": relative_path,
                    "modified_at": self._iso_timestamp(modified_at),
                    "size_bytes": file_size,
                    "size_formatted": self._format_bytes(file_size),
                }
                for (
                    modified_at,
                    _normalized_path,
                    relative_path,
                    file_size,
                ) in sorted(recent_files, reverse=True)
            ]

        return result

    def _directory_details(self, directory, home_directory):
        """Collect cheap directory and containing-filesystem context."""
        directory_stat = os.stat(directory)
        disk = shutil.disk_usage(directory)
        used_percent = round((disk.used / disk.total) * 100, 2) if disk.total else 0
        return {
            "directory": {
                "modified_at": self._iso_timestamp(directory_stat.st_mtime),
                "readable": os.access(directory, os.R_OK),
                "writable": os.access(directory, os.W_OK),
                "searchable": os.access(directory, os.X_OK),
                "is_home_directory": self._same_path(directory, home_directory),
                "is_filesystem_root": self._same_path(
                    directory,
                    Path(directory).anchor or os.path.sep,
                ),
            },
            "filesystem": {
                "total_bytes": disk.total,
                "total_formatted": self._format_bytes(disk.total),
                "used_bytes": disk.used,
                "used_formatted": self._format_bytes(disk.used),
                "free_bytes": disk.free,
                "free_formatted": self._format_bytes(disk.free),
                "used_percent": used_percent,
            },
        }

    @staticmethod
    def _same_path(first, second):
        """Compare absolute paths without requiring either path to resolve."""
        return os.path.normcase(os.path.abspath(first)) == os.path.normcase(
            os.path.abspath(second)
        )

    @classmethod
    def _home_relative_path(cls, directory, home_directory):
        """Return a home-relative display path only when truly inside home."""
        try:
            common = os.path.commonpath(
                [os.path.abspath(directory), os.path.abspath(home_directory)]
            )
        except ValueError:
            return None
        if not cls._same_path(common, home_directory):
            return None
        relative = os.path.relpath(directory, home_directory)
        if relative == ".":
            return "~"
        return "~{}{}".format(os.path.sep, relative)

    def execute(self, full=True, size=False, details=False, limit=10):
        """
        Show the current directory and a token-saving filesystem summary.

        Args:
            full (bool): Display the full path instead of only its final name.
            size (bool): Recursively calculate logical size and descendant totals.
            details (bool): Add rich previews and recursive aggregate analysis.
            limit (int): Maximum entries in each details list, from 1 through 100.

        Returns:
            A structured path and immediate inventory. Recursive fields are
            included only when ``size`` or ``details`` is requested.
        """
        if not 1 <= limit <= 100:
            return {
                "success": False,
                "error_code": "invalid_limit",
                "error": "limit must be between 1 and 100",
                "message": (
                    "Could not inspect the current directory: --limit must be "
                    "an integer between 1 and 100."
                ),
                "details": {
                    "received_limit": limit,
                    "minimum": 1,
                    "maximum": 100,
                },
            }

        try:
            current_dir = os.getcwd()
            parent_dir = os.path.dirname(current_dir)
            directory_name = (
                os.path.basename(os.path.normpath(current_dir)) or current_dir
            )
            home_dir = os.path.expanduser("~")
            home_relative = self._home_relative_path(current_dir, home_dir)
            displayed_dir = current_dir if full else directory_name

            contents = self._scan_current_level(
                current_dir,
                include_preview=details,
                limit=limit,
            )
            message = (
                "Current directory: {}. At this level: {}, {}, {}, {} " "({} total)."
            ).format(
                displayed_dir,
                self._counted_noun(contents["file_count"], "file"),
                self._counted_noun(
                    contents["directory_count"],
                    "directory",
                    "directories",
                ),
                self._counted_noun(
                    contents["symlink_count"],
                    "symbolic link",
                ),
                self._counted_noun(
                    contents["other_count"],
                    "other entry",
                    "other entries",
                ),
                contents["entry_count"],
            )
            if full and home_relative:
                message += " Home-relative path: {}.".format(home_relative)
            elif not full:
                message += " Full path: {}.".format(current_dir)

            result = {
                "success": True,
                "current_dir": current_dir,
                "full_path": bool(full),
                "displayed_path": displayed_dir,
                "directory_name": directory_name,
                "parent_directory": parent_dir,
                "contents": contents,
                "analysis_requested": {
                    "size": bool(size),
                    "details": bool(details),
                    "list_limit": limit,
                },
                "message": message,
            }
            if home_relative:
                result["home_relative_path"] = home_relative

            if size or details:
                recursive = self._scan_recursive(
                    current_dir,
                    include_details=details,
                    limit=limit,
                )
                result["recursive_analysis"] = recursive
                message += (
                    " Recursive total: {} across {} files and {} directories.".format(
                        recursive["total_size_formatted"],
                        recursive["file_count"],
                        recursive["directory_count"],
                    )
                )
                if not recursive["scan_complete"]:
                    message += (
                        " The recursive scan was partial due to {} errors.".format(
                            recursive["scan_error_count"]
                        )
                    )
                result["message"] = message

            if details:
                result.update(
                    self._directory_details(
                        current_dir,
                        home_dir,
                    )
                )

            if not contents["scan_complete"]:
                result.setdefault("warnings", []).append(
                    {
                        "code": "current_level_scan_partial",
                        "message": (
                            "Some entries could not be inspected; current-level "
                            "counts may be incomplete."
                        ),
                    }
                )

            return result
        except Exception as exc:
            return {
                "success": False,
                "error_code": "current_directory_inspection_failed",
                "error": "{}: {}".format(type(exc).__name__, str(exc)),
                "message": (
                    "Failed to retrieve current directory information: {}"
                ).format(str(exc)),
            }
