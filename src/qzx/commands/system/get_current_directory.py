#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
GetCurrentDirectory Command - Shows the current working directory and its contents
"""

from datetime import datetime, timezone

from qzx.commands.system._current_directory_context import (
    directory_details,
    execute_current_directory,
    home_relative_path,
    same_path,
)
from qzx.commands.system._current_directory_scan import (
    entry_type,
    is_hidden,
    record_scan_error,
    scan_current_level,
    scan_recursive,
)
from qzx.core.command_base import CommandBase


class GetCurrentDirectoryCommand(CommandBase):
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

    name = "getCurrentDirectory"
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
            "command": "qzx getCurrentDirectory",
            "description": (
                "Shows the current path and counts files/directories at that level"
            ),
        },
        {
            "command": "qzx getCurrentDirectory --size",
            "description": (
                "Adds recursive size and descendant totals in one filesystem scan"
            ),
        },
        {
            "command": "qzx getCurrentDirectory --details --limit 20",
            "description": (
                "Returns a rich directory analysis with up to 20 items per list"
            ),
        },
        {
            "command": "qzx getCurrentDirectory --full false",
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
        return entry_type(entry)

    @staticmethod
    def _is_hidden(entry, entry_stat=None):
        """Recognize portable dotfiles and the Windows hidden-file attribute."""
        return is_hidden(entry, entry_stat)

    @staticmethod
    def _record_scan_error(errors, path, error, limit):
        """Count every scan error while keeping only a bounded sample."""
        return record_scan_error(errors, path, error, limit)

    def _scan_current_level(self, directory, include_preview, limit):
        """Count and optionally preview the directory's immediate children."""
        return scan_current_level(
            directory,
            include_preview,
            limit,
            self._PROJECT_MARKERS,
            self._format_bytes,
            self._iso_timestamp,
        )

    def _scan_recursive(self, directory, include_details, limit):
        """Perform one bounded-memory recursive analysis."""
        return scan_recursive(
            directory,
            include_details,
            limit,
            self._format_bytes,
            self._iso_timestamp,
        )

    def _directory_details(self, directory, home_directory):
        """Collect directory and containing-filesystem context."""
        return directory_details(
            directory,
            home_directory,
            self._format_bytes,
            self._iso_timestamp,
        )

    @staticmethod
    def _same_path(first, second):
        """Compare absolute paths without requiring either path to resolve."""
        return same_path(first, second)

    @classmethod
    def _home_relative_path(cls, directory, home_directory):
        """Return a home-relative display path only when truly inside home."""
        return home_relative_path(directory, home_directory)

    def execute(self, full=True, size=False, details=False, limit=10):
        """Show the current directory and a token-saving filesystem summary."""
        return execute_current_directory(self, full, size, details, limit)
