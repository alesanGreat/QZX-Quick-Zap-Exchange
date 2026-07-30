#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""CompressZip Command - Creates ZIP archives without risking prior output."""

import fnmatch
import hashlib
import os
import tempfile
import zipfile

from qzx.core.command_base import CommandBase


class CompressZipCommand(CommandBase):
    """Create a ZIP in a sibling staging file and commit it atomically."""

    name = "compressZip"
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
            "command": "qzx compressZip project.zip .",
            "description": (
                "Compress the current directory into a new project.zip"
            ),
        },
        {
            "command": "qzx compressZip src.zip src",
            "description": "Compress the src folder into a new src.zip",
        },
        {
            "command": "qzx compressZip project.zip . --overwrite",
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

    @staticmethod
    def _sha256(path):
        digest = hashlib.sha256()
        with open(path, "rb") as archive_file:
            for chunk in iter(lambda: archive_file.read(65536), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def execute(
        self,
        zip_path,
        source_path,
        exclude_patterns=None,
        overwrite=False,
    ):
        """Compress one source while preserving any prior destination."""
        if not str(zip_path).strip() or not str(source_path).strip():
            return self._error(
                "parameters_required",
                "Both zip_path and source_path parameters are required.",
                "Both ZIP destination and source path must be set.",
            )
        if isinstance(overwrite, str):
            parsed_overwrite = self._parse_bool(overwrite)
            if parsed_overwrite is None:
                return self._error(
                    "invalid_overwrite",
                    f"Invalid overwrite value: {overwrite}",
                    (
                        "overwrite must be true or false; received "
                        f"'{overwrite}'."
                    ),
                    overwrite=overwrite,
                )
            overwrite = parsed_overwrite

        absolute_source = os.path.abspath(str(source_path).strip())
        absolute_zip = os.path.abspath(str(zip_path).strip())
        source_failure = self._validate_source(
            absolute_source,
            absolute_zip,
        )
        if source_failure is not None:
            return source_failure
        if os.path.isdir(absolute_zip) and not os.path.islink(absolute_zip):
            return self._error(
                "destination_is_directory",
                f"ZIP destination is a directory: {absolute_zip}",
                f"Choose a ZIP file path instead of '{absolute_zip}'.",
                zip_path=absolute_zip,
            )
        if os.path.lexists(absolute_zip) and not overwrite:
            return self._error(
                "destination_exists",
                f"ZIP destination already exists: {absolute_zip}",
                (
                    f"ZIP destination '{absolute_zip}' already exists. Use "
                    "--overwrite to replace it after a safety backup."
                ),
                zip_path=absolute_zip,
                overwrite=False,
            )

        if exclude_patterns is None:
            excludes = {
                ".git",
                "node_modules",
                "__pycache__",
                ".venv",
                "env",
                "dist",
                "build",
            }
        else:
            excludes = {
                pattern.strip()
                for pattern in str(exclude_patterns).split(",")
                if pattern.strip()
            }

        try:
            import zlib  # noqa: F401

            compression = zipfile.ZIP_DEFLATED
        except ImportError:
            compression = zipfile.ZIP_STORED

        temporary_zip = None
        try:
            zip_directory = os.path.dirname(absolute_zip)
            if zip_directory:
                os.makedirs(zip_directory, exist_ok=True)
            descriptor, temporary_zip = tempfile.mkstemp(
                prefix=".qzx-compress-",
                suffix=".zip.part",
                dir=zip_directory or None,
            )
            os.close(descriptor)

            total_files = 0
            original_size = 0
            skipped_symlinks = []
            with zipfile.ZipFile(
                temporary_zip,
                "w",
                compression=compression,
                allowZip64=True,
            ) as archive:
                if os.path.isfile(absolute_source):
                    archive.write(
                        absolute_source,
                        os.path.basename(absolute_source),
                    )
                    original_size = os.path.getsize(absolute_source)
                    total_files = 1
                else:
                    for root, directories, files in os.walk(
                        absolute_source,
                        followlinks=False,
                    ):
                        directories[:] = [
                            directory
                            for directory in directories
                            if not os.path.islink(
                                os.path.join(root, directory)
                            )
                            and directory not in excludes
                            and not any(
                                fnmatch.fnmatch(directory, pattern)
                                for pattern in excludes
                            )
                        ]
                        for filename in files:
                            if filename in excludes or any(
                                fnmatch.fnmatch(filename, pattern)
                                for pattern in excludes
                            ):
                                continue
                            full_path = os.path.join(root, filename)
                            if os.path.islink(full_path):
                                skipped_symlinks.append(
                                    os.path.relpath(
                                        full_path,
                                        absolute_source,
                                    )
                                )
                                continue
                            if self._same_filesystem_object(
                                full_path,
                                absolute_zip,
                            ) or self._same_filesystem_object(
                                full_path,
                                temporary_zip,
                            ):
                                continue
                            archive_name = os.path.relpath(
                                full_path,
                                absolute_source,
                            )
                            archive.write(full_path, archive_name)
                            original_size += os.path.getsize(full_path)
                            total_files += 1

            compressed_size = os.path.getsize(temporary_zip)
            archive_sha256 = self._sha256(temporary_zip)
            os.replace(temporary_zip, absolute_zip)
            temporary_zip = None

            ratio = (
                (1 - compressed_size / original_size) * 100
                if original_size > 0
                else 0
            )
            readable_original = self._format_bytes(original_size)
            readable_compressed = self._format_bytes(compressed_size)
            message = (
                f"Archived {total_files:,} file(s) from '{absolute_source}' "
                f"to '{absolute_zip}' ({readable_original} → "
                f"{readable_compressed}, SHA-256 {archive_sha256})."
            )
            if skipped_symlinks:
                message += (
                    f" Skipped {len(skipped_symlinks):,} symbolic link(s) "
                    "to keep archive boundaries explicit."
                )
            return {
                "success": True,
                "zip_path": absolute_zip,
                "source_path": absolute_source,
                "files_archived": total_files,
                "original_bytes": original_size,
                "compressed_bytes": compressed_size,
                "compression_ratio_percent": round(ratio, 2),
                "sha256": archive_sha256,
                "overwrite": bool(overwrite),
                "skipped_symlinks": skipped_symlinks,
                "message": message,
            }
        except Exception as exc:
            return self._error(
                "compression_failed",
                f"{type(exc).__name__}: {exc}",
                (
                    "ZIP compression failed before the destination was "
                    f"replaced: {exc}"
                ),
                zip_path=absolute_zip,
                source_path=absolute_source,
                prior_destination_preserved=True,
            )
        finally:
            if temporary_zip and os.path.exists(temporary_zip):
                os.unlink(temporary_zip)
