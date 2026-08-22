#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Inspect directory emptiness with streaming, stable, link-safe evidence."""

from __future__ import annotations

import os
import stat

from qzx.core.command_base import CommandBase
from qzx.core.file_content_analysis import (
    DirectoryChangedDuringScanError,
    directory_fingerprint,
    normalize_boolean,
    validate_directory,
)


class IsDirectoryEmptyCommand(CommandBase):
    """Check one stable real directory without materializing its listing."""

    name = "isDirectoryEmpty"
    description = (
        "Checks stable directory emptiness with streaming counts, explicit "
        "hidden-item policy, and no symbolic-link traversal by default"
    )
    category = "file"

    parameters = [
        {
            "name": "directory_path",
            "description": "Path to the real directory to inspect",
            "required": True,
            "type": "str",
        },
        {
            "name": "include_hidden",
            "description": (
                "Count dot-prefixed and platform-hidden entries when deciding "
                "whether the directory is empty"
            ),
            "required": False,
            "default": False,
            "type": "bool",
        },
        {
            "name": "follow_symlinks",
            "description": (
                "Follow reviewed symbolic-link or junction components to their "
                "resolved directory target"
            ),
            "required": False,
            "default": False,
            "type": "bool",
        },
    ]

    examples = [
        {
            "command": "qzx isDirectoryEmpty /path/to/directory",
            "description": "Check visible emptiness without following links",
        },
        {
            "command": "qzx isDirectoryEmpty /path/to/directory true",
            "description": "Include hidden entries in the emptiness decision",
        },
        {
            "command": "qzx isDirectoryEmpty reviewed-link true true",
            "description": "Inspect an explicitly reviewed linked directory target",
        },
    ]

    def __init__(self, *, scandir=None, hidden_predicate=None):
        super().__init__()
        self._scandir = scandir or os.scandir
        self._hidden_predicate = hidden_predicate or self._is_hidden_entry

    def execute(
        self,
        directory_path,
        include_hidden=False,
        follow_symlinks=False,
    ):
        """Return exact counts only when the directory remains stable."""
        include_hidden, error = normalize_boolean(
            include_hidden,
            field="include_hidden",
            command_base=self,
        )
        if error is not None:
            return error
        follow_links, error = normalize_boolean(
            follow_symlinks,
            field="follow_symlinks",
            command_base=self,
        )
        if error is not None:
            return error

        target, error = validate_directory(
            directory_path,
            follow_symlinks=follow_links,
        )
        if error is not None:
            return error

        counts = self._empty_counts()
        error_samples = []
        try:
            initial_fingerprint = directory_fingerprint(target.analyzed_path)
            if initial_fingerprint != target.fingerprint:
                raise DirectoryChangedDuringScanError(
                    "The directory changed between validation and enumeration."
                )
            with self._scandir(target.analyzed_path) as entries:
                for entry in entries:
                    counts["total_entries"] += 1
                    hidden = False
                    try:
                        hidden = bool(self._hidden_predicate(entry))
                    except (OSError, RuntimeError, ValueError) as exc:
                        self._record_scan_error(
                            counts,
                            error_samples,
                            entry.path,
                            "hidden_attribute",
                            exc,
                        )

                    if hidden and not include_hidden:
                        counts["ignored_hidden_entries"] += 1
                        continue

                    counts["considered_entries"] += 1
                    try:
                        entry_type = self._entry_type(entry)
                    except OSError as exc:
                        counts["unavailable_count"] += 1
                        self._record_scan_error(
                            counts,
                            error_samples,
                            entry.path,
                            "entry_type",
                            exc,
                        )
                        continue
                    counts[f"{entry_type}_count"] += 1
            final_fingerprint = directory_fingerprint(target.analyzed_path)
            if final_fingerprint != initial_fingerprint:
                raise DirectoryChangedDuringScanError(
                    "The directory changed while entries were being enumerated."
                )
        except DirectoryChangedDuringScanError as exc:
            return self._changed_failure(
                target,
                counts,
                error_samples,
                exc,
            )
        except OSError as exc:
            return {
                "success": False,
                "error_code": "directory_scan_failed",
                "error": f"{type(exc).__name__}: {exc}",
                "message": (
                    f"QZX could not scan directory '{target.analyzed_path}'."
                ),
                "directory_path": str(target.absolute_path),
                "analyzed_path": str(target.analyzed_path),
                "details": {
                    "target": target.evidence(),
                    **counts,
                    "scan_complete": False,
                    "symbolic_links_followed_inside_directory": False,
                },
            }

        is_empty = counts["considered_entries"] == 0
        scan_complete = counts["scan_error_count"] == 0
        details = {
            "target": target.evidence(),
            **counts,
            "scan_complete": scan_complete,
            "directory_stable_during_scan": True,
            "hidden_policy": (
                "included" if include_hidden else "ignored_for_emptiness"
            ),
            "symbolic_links_followed_inside_directory": False,
            "entry_classification": (
                "regular_files_directories_links_other_unavailable"
            ),
        }
        if error_samples:
            details["scan_error_samples"] = error_samples

        if is_empty:
            message = (
                f"Directory '{target.absolute_path}' is empty under the selected "
                "hidden-item policy."
            )
        else:
            message = (
                f"Directory '{target.absolute_path}' is not empty: "
                f"{counts['considered_entries']} considered entries "
                f"({counts['file_count']} files, "
                f"{counts['directory_count']} directories, "
                f"{counts['symlink_count']} links, "
                f"{counts['other_count']} other)."
            )
        if counts["ignored_hidden_entries"]:
            message += (
                f" {counts['ignored_hidden_entries']} hidden entries were "
                "ignored for the emptiness decision."
            )

        result = {
            "success": True,
            "message": message,
            "directory_path": str(target.absolute_path),
            "analyzed_path": str(target.analyzed_path),
            "is_empty": is_empty,
            "include_hidden": include_hidden,
            "item_count": counts["considered_entries"],
            "file_count": counts["file_count"],
            "directory_count": counts["directory_count"],
            "symlink_count": counts["symlink_count"],
            "details": details,
        }
        if not scan_complete:
            result["warnings"] = [
                "One or more entries could not be fully classified; they still "
                "counted as present, and bounded error evidence is available."
            ]
        return result

    @staticmethod
    def _empty_counts():
        return {
            "total_entries": 0,
            "considered_entries": 0,
            "ignored_hidden_entries": 0,
            "file_count": 0,
            "directory_count": 0,
            "symlink_count": 0,
            "other_count": 0,
            "unavailable_count": 0,
            "scan_error_count": 0,
        }

    @staticmethod
    def _is_hidden_entry(entry):
        if entry.name.startswith("."):
            return True
        entry_stat = entry.stat(follow_symlinks=False)
        hidden_flag = getattr(stat, "FILE_ATTRIBUTE_HIDDEN", 0x2)
        file_attributes = getattr(entry_stat, "st_file_attributes", 0)
        return bool(file_attributes & hidden_flag)

    @staticmethod
    def _entry_type(entry):
        is_junction = getattr(os.path, "isjunction", None)
        if entry.is_symlink() or (
            is_junction is not None and is_junction(entry.path)
        ):
            return "symlink"
        if entry.is_file(follow_symlinks=False):
            return "file"
        if entry.is_dir(follow_symlinks=False):
            return "directory"
        return "other"

    @staticmethod
    def _record_scan_error(
        counts,
        error_samples,
        path,
        phase,
        error,
    ):
        counts["scan_error_count"] += 1
        if len(error_samples) < 20:
            error_samples.append(
                {
                    "path": str(path),
                    "phase": phase,
                    "error_type": type(error).__name__,
                    "error": str(error),
                }
            )

    @staticmethod
    def _changed_failure(target, counts, error_samples, error):
        details = {
            "target": target.evidence(),
            **counts,
            "scan_complete": False,
            "directory_stable_during_scan": False,
            "symbolic_links_followed_inside_directory": False,
        }
        if error_samples:
            details["scan_error_samples"] = error_samples
        return {
            "success": False,
            "error_code": "directory_changed_during_scan",
            "error": f"{type(error).__name__}: {error}",
            "message": (
                f"Directory '{target.absolute_path}' changed during enumeration, "
                "so QZX did not publish an emptiness conclusion."
            ),
            "directory_path": str(target.absolute_path),
            "analyzed_path": str(target.analyzed_path),
            "details": details,
        }
