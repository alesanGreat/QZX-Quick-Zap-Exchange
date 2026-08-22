#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Create directories with exact per-path evidence and safe partial rollback."""

from __future__ import annotations

import os
import stat
from pathlib import Path

from qzx.core.command_base import CommandBase


class CreateDirectoryCommand(CommandBase):
    """Create one or more real directories without traversing path links."""

    name = "createDirectory"
    description = (
        "Creates one or more real directories with deduplication, conflict "
        "detection, and per-target rollback on failure"
    )
    category = "file"
    MAX_PATHS = 1_000

    parameters = [
        {
            "name": "directory_paths",
            "description": "One or more real directory paths to create",
            "required": True,
            "type": "str",
            "is_variadic": True,
        }
    ]

    examples = [
        {
            "command": 'qzx createDirectory "ProjectFolder"',
            "description": 'Create one directory named "ProjectFolder"',
        },
        {
            "command": (
                'qzx createDirectory "src/components" "src/styles" "src/utils"'
            ),
            "description": (
                "Create several project directories and report every target "
                "independently"
            ),
        },
    ]

    def __init__(self, *, mkdir=None, rmdir=None):
        super().__init__()
        self._mkdir = mkdir or os.mkdir
        self._rmdir = rmdir or os.rmdir

    def execute(self, *directory_paths):
        """Create each unique path while preserving reviewable batch evidence."""
        if not directory_paths:
            return {
                "success": False,
                "error_code": "missing_argument",
                "error": "No directory paths were provided.",
                "message": "Provide at least one directory path to create.",
            }
        if len(directory_paths) > self.MAX_PATHS:
            return {
                "success": False,
                "error_code": "too_many_paths",
                "error": (
                    f"createDirectory accepts at most {self.MAX_PATHS} paths per "
                    f"invocation; received {len(directory_paths)}."
                ),
                "message": "Split this directory batch into smaller invocations.",
                "details": {
                    "requested_count": len(directory_paths),
                    "maximum_path_count": self.MAX_PATHS,
                    "filesystem_changed": False,
                },
            }

        operations = []
        first_request_by_identity = {}
        for request_index, requested_path in enumerate(directory_paths, start=1):
            normalized, requested_text, error = self._normalize_path(requested_path)
            if error is not None:
                operations.append(
                    {
                        "request_index": request_index,
                        "requested_path": requested_text,
                        "status": "failed",
                        "changed": False,
                        **error,
                    }
                )
                continue

            identity = os.path.normcase(os.path.normpath(str(normalized)))
            duplicate_of = first_request_by_identity.get(identity)
            if duplicate_of is not None:
                operations.append(
                    {
                        "request_index": request_index,
                        "requested_path": requested_text,
                        "path": str(normalized),
                        "status": "duplicate",
                        "changed": False,
                        "duplicate_of_request_index": duplicate_of,
                    }
                )
                continue
            first_request_by_identity[identity] = request_index
            operations.append(
                self._create_one(
                    normalized,
                    requested_text=requested_text,
                    request_index=request_index,
                )
            )

        counts = {
            "requested": len(directory_paths),
            "normalized_unique": len(first_request_by_identity),
            "created": sum(
                operation["status"] == "created" for operation in operations
            ),
            "already_existed": sum(
                operation["status"] == "already_exists" for operation in operations
            ),
            "duplicates": sum(
                operation["status"] == "duplicate" for operation in operations
            ),
            "failed": sum(
                operation["status"] == "failed" for operation in operations
            ),
            "directories_created": sum(
                len(operation.get("created_paths", [])) for operation in operations
            ),
            "directories_rolled_back": sum(
                len(operation.get("rolled_back_paths", []))
                for operation in operations
            ),
            "directories_retained_after_command": sum(
                len(operation.get("created_paths", []))
                if operation.get("status") == "created"
                else len(operation.get("remaining_created_paths", []))
                for operation in operations
            ),
        }
        filesystem_changed = any(operation["changed"] for operation in operations)
        details = {
            **counts,
            "filesystem_changed": filesystem_changed,
            "link_traversal_allowed": False,
            "rollback_policy": "empty_directories_created_by_a_failed_target",
            "operations": operations,
        }

        if counts["failed"]:
            completed = counts["created"] + counts["already_existed"]
            error_code = (
                "partial_directory_creation"
                if completed
                else "directory_creation_failed"
            )
            return {
                "success": False,
                "error_code": error_code,
                "error": (
                    f"{counts['failed']} of {len(operations)} path request"
                    f"{'s' if len(operations) != 1 else ''} failed."
                ),
                "message": (
                    f"Created {counts['created']} target director"
                    f"{'ies' if counts['created'] != 1 else 'y'}; "
                    f"{counts['already_existed']} already existed, "
                    f"{counts['duplicates']} duplicate"
                    f"{'s' if counts['duplicates'] != 1 else ''} were skipped, "
                    f"and {counts['failed']} failed."
                ),
                "details": details,
            }

        return {
            "success": True,
            "message": (
                f"Created {counts['created']} target director"
                f"{'ies' if counts['created'] != 1 else 'y'}; "
                f"{counts['already_existed']} already existed and "
                f"{counts['duplicates']} duplicate"
                f"{'s' if counts['duplicates'] != 1 else ''} were skipped."
            ),
            "details": details,
        }

    @staticmethod
    def _normalize_path(requested_path):
        requested_text = repr(requested_path)
        try:
            raw_path = os.fspath(requested_path)
        except TypeError:
            return None, requested_text, {
                "error_code": "invalid_directory_path",
                "error": "Directory paths must be text or path-like objects.",
            }
        if not isinstance(raw_path, str):
            return None, requested_text, {
                "error_code": "invalid_directory_path",
                "error": "Directory paths must resolve to text, not raw bytes.",
            }
        requested_text = raw_path
        if not raw_path:
            return None, requested_text, {
                "error_code": "invalid_directory_path",
                "error": "Directory paths must not be empty.",
            }
        if "\x00" in raw_path:
            return None, requested_text, {
                "error_code": "invalid_directory_path",
                "error": "Directory paths must not contain NUL bytes.",
            }
        try:
            expanded = os.path.expanduser(raw_path)
            normalized = Path(os.path.abspath(expanded))
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            return None, requested_text, {
                "error_code": "invalid_directory_path",
                "error": f"{type(exc).__name__}: {exc}",
            }
        return normalized, requested_text, None

    def _create_one(self, path, *, requested_text, request_index):
        base = {
            "request_index": request_index,
            "requested_path": requested_text,
            "path": str(path),
        }
        components = list(self._path_components(path))
        missing_components = []
        try:
            for component in components:
                entry_type = self._path_type(component)
                if entry_type == "missing":
                    missing_components.append(component)
                    continue
                if entry_type == "link":
                    return {
                        **base,
                        "status": "failed",
                        "changed": False,
                        "error_code": "symlink_path_blocked",
                        "error": (
                            "Directory creation does not traverse symbolic links or "
                            f"junctions; blocked component '{component}'."
                        ),
                        "blocked_component": str(component),
                    }
                if component != path and entry_type != "directory":
                    return {
                        **base,
                        "status": "failed",
                        "changed": False,
                        "error_code": "parent_not_directory",
                        "error": (
                            f"Parent component '{component}' is {entry_type}, not a "
                            "directory."
                        ),
                        "blocked_component": str(component),
                        "blocked_component_type": entry_type,
                    }
                if component == path:
                    if entry_type == "directory":
                        return {
                            **base,
                            "status": "already_exists",
                            "changed": False,
                            "created_paths": [],
                        }
                    return {
                        **base,
                        "status": "failed",
                        "changed": False,
                        "error_code": "path_conflict",
                        "error": (
                            f"Target '{path}' already exists as {entry_type}, not a "
                            "directory."
                        ),
                        "existing_type": entry_type,
                    }
        except OSError as exc:
            return {
                **base,
                "status": "failed",
                "changed": False,
                "error_code": "path_inspection_failed",
                "error": f"{type(exc).__name__}: {exc}",
            }

        created_paths = []
        concurrent_directories = []
        for component in missing_components:
            try:
                self._mkdir(component)
                created_paths.append(component)
            except FileExistsError:
                try:
                    concurrent_type = self._path_type(component)
                except OSError as exc:
                    return self._creation_failure(
                        base,
                        path,
                        created_paths,
                        "path_inspection_failed",
                        exc,
                    )
                if concurrent_type == "directory":
                    concurrent_directories.append(component)
                    continue
                return self._creation_failure(
                    base,
                    path,
                    created_paths,
                    "concurrent_path_conflict",
                    FileExistsError(
                        f"'{component}' concurrently became {concurrent_type}."
                    ),
                )
            except OSError as exc:
                return self._creation_failure(
                    base,
                    path,
                    created_paths,
                    "directory_create_failed",
                    exc,
                )

        try:
            final_type = self._path_type(path)
        except OSError as exc:
            return self._creation_failure(
                base,
                path,
                created_paths,
                "path_inspection_failed",
                exc,
            )
        if final_type != "directory":
            return self._creation_failure(
                base,
                path,
                created_paths,
                "directory_verification_failed",
                OSError(f"Target verified as {final_type}, not directory."),
            )

        return {
            **base,
            "status": "created" if created_paths else "already_exists",
            "changed": bool(created_paths),
            "created_paths": [str(component) for component in created_paths],
            "concurrent_directories": [
                str(component) for component in concurrent_directories
            ],
        }

    def _creation_failure(
        self,
        base,
        target,
        created_paths,
        error_code,
        error,
    ):
        rolled_back = []
        rollback_errors = []
        for component in reversed(created_paths):
            try:
                self._rmdir(component)
                rolled_back.append(component)
            except OSError as rollback_error:
                rollback_errors.append(
                    {
                        "path": str(component),
                        "error_type": type(rollback_error).__name__,
                        "error": str(rollback_error),
                    }
                )

        remaining = [
            component for component in created_paths if os.path.lexists(component)
        ]
        return {
            **base,
            "status": "failed",
            "changed": bool(remaining),
            "error_code": error_code,
            "error": (
                f"Could not create directory '{target}': "
                f"{type(error).__name__}: {error}"
            ),
            "created_paths": [str(component) for component in created_paths],
            "rolled_back_paths": [str(component) for component in rolled_back],
            "remaining_created_paths": [str(component) for component in remaining],
            "rollback_errors": rollback_errors,
        }

    @staticmethod
    def _path_components(path):
        parts = path.parts
        if not parts:
            return
        current = Path(path.anchor)
        yield current
        for part in parts[1:]:
            current /= part
            yield current

    @staticmethod
    def _path_type(path):
        if not os.path.lexists(path):
            return "missing"
        is_junction = getattr(os.path, "isjunction", None)
        if os.path.islink(path) or (
            is_junction is not None and is_junction(path)
        ):
            return "link"
        mode = os.lstat(path).st_mode
        if stat.S_ISDIR(mode):
            return "directory"
        if stat.S_ISREG(mode):
            return "file"
        return "special entry"
