#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""CreateZip Command - Creates ZIP archives without risking prior output."""

import os

from qzx.commands.file._create_zip_workflow import (
    create_zip_archive,
    prepare_create_zip_request,
)
from qzx.core.command_base import CommandBase


class CreateZipCommand(CommandBase):
    """Create a ZIP in a sibling staging file and commit it atomically."""

    name = "createZip"
    description = (
        "Compresses a file or directory into an atomic ZIP archive with "
        "custom exclusion rules"
    )
    category = "file"
    requires_explicit_approval = True
    approval_when_parameter = "overwrite"
    backup_target_parameter = "zip_path"
    _byte_units = ("B", "KB", "MB", "GB")

    parameters = [
        {
            "name": "zip_path",
            "description": (
                "Target path for the created ZIP archive (e.g. project.zip)"
            ),
            "required": True,
        },
        {
            "name": "source_path",
            "description": "Local file or directory to compress",
            "required": True,
        },
        {
            "name": "exclude_patterns",
            "description": (
                "Comma-separated folders, files, or wildcards to exclude "
                "(defaults to standard caches)"
            ),
            "required": False,
            "default": ".git,node_modules,__pycache__,.venv,env,dist,build",
        },
        {
            "name": "overwrite",
            "description": (
                "Replace an existing ZIP after creating a safety backup"
            ),
            "required": False,
            "default": False,
        },
    ]

    examples = [
        {
            "command": "qzx createZip project.zip .",
            "description": (
                "Compress the current directory into a new project.zip"
            ),
        },
        {
            "command": "qzx createZip src.zip src",
            "description": "Compress the src folder into a new src.zip",
        },
        {
            "command": "qzx createZip project.zip . --overwrite",
            "description": (
                "Replace project.zip after creating a safety backup"
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

    @staticmethod
    def _same_filesystem_object(first, second):
        try:
            return os.path.samefile(first, second)
        except OSError:
            return (
                os.path.normcase(os.path.realpath(first))
                == os.path.normcase(os.path.realpath(second))
            )

    def _validate_source(self, source_path, zip_path):
        if not str(source_path).strip():
            return self._error(
                "source_required",
                "The source_path parameter is required.",
                "Source path is required.",
            )
        absolute_source = os.path.abspath(str(source_path).strip())
        absolute_zip = os.path.abspath(str(zip_path).strip())
        if not os.path.lexists(absolute_source):
            return self._error(
                "source_not_found",
                f"Source path '{source_path}' does not exist.",
                f"Source path '{source_path}' does not exist.",
                source_path=absolute_source,
            )
        if os.path.islink(absolute_source):
            return self._error(
                "source_is_symlink",
                f"Source path is a symbolic link: {absolute_source}",
                (
                    "The top-level source cannot be a symbolic link. Choose "
                    "the real file or directory to make archive contents "
                    "explicit."
                ),
                source_path=absolute_source,
            )
        if self._same_filesystem_object(absolute_source, absolute_zip):
            return self._error(
                "source_equals_destination",
                "Source and ZIP destination resolve to the same path.",
                (
                    "Source and ZIP destination identify the same filesystem "
                    "object. Choose a different ZIP path."
                ),
                source_path=absolute_source,
                zip_path=absolute_zip,
            )
        return None

    def validate_safety_backup_target(self, target, values):
        """Avoid a pointless backup or one taken for an invalid source."""
        source_failure = self._validate_source(
            values.get("source_path"),
            target,
        )
        if source_failure is not None:
            return source_failure
        if not os.path.lexists(target):
            return self._error(
                "overwrite_target_missing",
                f"Cannot overwrite missing ZIP destination: {target}",
                (
                    f"ZIP destination '{target}' does not exist. Omit "
                    "--overwrite to create a new archive."
                ),
                zip_path=os.path.abspath(target),
                overwrite=True,
            )
        if os.path.isdir(target) and not os.path.islink(target):
            return self._error(
                "destination_is_directory",
                f"ZIP destination is a directory: {target}",
                f"Choose a file path instead of directory '{target}'.",
                zip_path=os.path.abspath(target),
                overwrite=True,
            )
        return None

    def execute(
        self,
        zip_path,
        source_path,
        exclude_patterns=None,
        overwrite=False,
    ):
        """Compress one source while preserving any prior destination."""
        request, failure = prepare_create_zip_request(
            self,
            zip_path,
            source_path,
            exclude_patterns,
            overwrite,
        )
        if failure is not None:
            return failure
        return create_zip_archive(self, request)
