#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ExtractZip Command - Extracts ZIP archives defensively.
"""

import os
import re
import shutil
import stat
import zipfile
from pathlib import PurePosixPath

from qzx.commands.file._zip_extraction_workflow import execute_extract
from qzx.commands.file._zip_member_validation import validate_archive_members
from qzx.core.command_base import CommandBase


class ExtractZipCommand(CommandBase):
    """Extract a ZIP archive only after validating every member."""

    name = "extractZip"
    description = (
        "Extracts files from a ZIP archive after validating paths, types, "
        "limits, and destination conflicts"
    )
    category = "file"
    requires_explicit_approval = True
    approval_when_parameter = "overwrite"
    backup_target_parameter = "target_path"
    _byte_units = ("B", "KB", "MB", "GB")
    _copy_chunk_size = 1024 * 1024

    parameters = [
        {
            "name": "zip_path",
            "description": "Path to the ZIP file to extract",
            "required": True,
        },
        {
            "name": "target_path",
            "description": (
                "Destination directory to extract files into "
                "(defaults to current directory)"
            ),
            "required": False,
            "default": ".",
        },
        {
            "name": "overwrite",
            "description": (
                "Replace conflicting destination entries after backing up "
                "the target directory"
            ),
            "required": False,
            "default": False,
        },
        {
            "name": "max_files",
            "description": "Maximum number of files accepted from the archive",
            "required": False,
            "default": 10000,
        },
        {
            "name": "max_total_size_mb",
            "description": (
                "Maximum total uncompressed size accepted, in mebibytes"
            ),
            "required": False,
            "default": 1024,
        },
    ]

    examples = [
        {
            "command": "qzx extractZip project.zip",
            "description": (
                "Extract project.zip without replacing existing files"
            ),
        },
        {
            "command": "qzx extractZip project.zip C:/extracted-app",
            "description": "Extract project.zip into C:/extracted-app",
        },
        {
            "command": (
                "qzx extractZip project.zip C:/extracted-app --overwrite"
            ),
            "description": (
                "Replace conflicts after creating a target-directory backup"
            ),
        },
    ]

    @staticmethod
    def _error(error_code, error, message, **details):
        return {
            "success": False,
            "error_code": error_code,
            "error": error,
            "message": message,
            "details": details,
        }

    @classmethod
    def _validate_archive_source(cls, zip_path):
        if not str(zip_path).strip():
            return cls._error(
                "zip_path_required",
                "The zip_path parameter is required.",
                "ZIP file path is required.",
            )
        absolute_zip = os.path.abspath(str(zip_path).strip())
        if not os.path.exists(absolute_zip):
            return cls._error(
                "zip_not_found",
                f"ZIP file '{zip_path}' does not exist.",
                f"ZIP file '{zip_path}' does not exist.",
                zip_path=absolute_zip,
            )
        if not os.path.isfile(absolute_zip):
            return cls._error(
                "zip_not_file",
                f"'{zip_path}' is not a file.",
                f"'{zip_path}' is not a file.",
                zip_path=absolute_zip,
            )
        if not zipfile.is_zipfile(absolute_zip):
            return cls._error(
                "invalid_zip",
                f"'{zip_path}' is not a valid ZIP archive.",
                f"'{zip_path}' is not a valid ZIP archive.",
                zip_path=absolute_zip,
            )
        return None

    def validate_safety_backup_target(self, target, values):
        """Require a valid archive and a real directory for --overwrite."""
        source_failure = self._validate_archive_source(values.get("zip_path"))
        if source_failure is not None:
            return source_failure
        if not os.path.lexists(target):
            return self._error(
                "overwrite_target_missing",
                f"Cannot overwrite missing target directory: {target}",
                (
                    f"Target directory '{target}' does not exist. Omit "
                    "--overwrite to create it without an unnecessary backup."
                ),
                target_path=os.path.abspath(target),
                overwrite=True,
            )
        if os.path.islink(target) or not os.path.isdir(target):
            return self._error(
                "invalid_target",
                f"Overwrite target is not a real directory: {target}",
                (
                    f"Target '{target}' must be an existing directory and "
                    "cannot be a symbolic link."
                ),
                target_path=os.path.abspath(target),
                overwrite=True,
            )
        return None

    @staticmethod
    def _member_parts(member):
        """Return portable path parts or a reason the member is unsafe."""
        raw_name = member.filename.replace("\\", "/")
        if "\x00" in raw_name:
            return None, "contains a null byte"
        pure_path = PurePosixPath(raw_name)
        if pure_path.is_absolute():
            return None, "uses an absolute path"
        parts = tuple(
            part for part in pure_path.parts if part not in {"", "."}
        )
        if not parts:
            return (), None
        if any(part == ".." for part in parts):
            return None, "escapes the target with '..'"
        if re.match(r"^[A-Za-z]:", parts[0]):
            return None, "uses a drive-qualified path"

        unix_mode = (member.external_attr >> 16) & 0xFFFF
        file_type = stat.S_IFMT(unix_mode)
        if file_type not in {0, stat.S_IFREG, stat.S_IFDIR}:
            return None, "uses a symbolic link or another special file type"
        return parts, None

    @staticmethod
    def _remove_path(path):
        if os.path.isdir(path) and not os.path.islink(path):
            shutil.rmtree(path)
        else:
            os.unlink(path)

    def _validated_members(
        self,
        archive,
        target_root,
        max_files,
        max_total_bytes,
    ):
        """Validate the whole central directory before writing anything."""
        return validate_archive_members(
            self,
            archive,
            target_root,
            max_files,
            max_total_bytes,
        )

    @staticmethod
    def _destination_conflicts(entries, target_root):
        conflicts = []
        for _member, parts, is_directory in entries:
            destination = target_root.joinpath(*parts)
            if os.path.lexists(destination):
                if is_directory and destination.is_dir():
                    continue
                conflicts.append(str(destination))
            for parent in destination.parents:
                if parent == target_root:
                    break
                if os.path.lexists(parent) and not parent.is_dir():
                    conflicts.append(str(parent))
                    break
        return sorted(set(conflicts))

    def execute(
        self,
        zip_path,
        target_path=".",
        overwrite=False,
        max_files=10000,
        max_total_size_mb=1024,
    ):
        """Validate, stage, and commit extraction of one ZIP archive."""
        return execute_extract(
            self,
            zip_path,
            target_path,
            overwrite,
            max_files,
            max_total_size_mb,
        )
