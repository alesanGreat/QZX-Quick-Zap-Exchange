#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
DecompressZip Command - Extracts ZIP archives defensively.
"""

import os
import re
import shutil
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

from qzx.core.command_base import CommandBase


class DecompressZipCommand(CommandBase):
    """Extract a ZIP archive only after validating every member."""

    name = "decompressZip"
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
            "command": "qzx decompressZip project.zip",
            "description": (
                "Extract project.zip without replacing existing files"
            ),
        },
        {
            "command": "qzx decompressZip project.zip C:/extracted-app",
            "description": "Extract project.zip into C:/extracted-app",
        },
        {
            "command": (
                "qzx decompressZip project.zip C:/extracted-app --overwrite"
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
        entries = []
        unsafe_members = []
        seen = set()
        file_paths = set()
        file_count = 0
        total_bytes = 0
        resolved_target = target_root.resolve(strict=False)

        for member in archive.infolist():
            parts, reason = self._member_parts(member)
            if reason is not None:
                unsafe_members.append(
                    {"member": member.filename, "reason": reason}
                )
                continue
            if not parts:
                continue

            relative_key = "/".join(parts)
            comparison_key = (
                relative_key.casefold() if os.name == "nt" else relative_key
            )
            if comparison_key in seen:
                unsafe_members.append(
                    {
                        "member": member.filename,
                        "reason": "duplicates another normalized member path",
                    }
                )
                continue
            seen.add(comparison_key)

            member_target = target_root.joinpath(*parts)
            try:
                member_target.resolve(strict=False).relative_to(
                    resolved_target
                )
            except ValueError:
                unsafe_members.append(
                    {
                        "member": member.filename,
                        "reason": "resolves outside the target directory",
                    }
                )
                continue

            is_directory = member.is_dir()
            if not is_directory:
                file_count += 1
                total_bytes += member.file_size
                file_paths.add(comparison_key)
            entries.append((member, parts, is_directory))

        for file_path in sorted(file_paths):
            components = file_path.split("/")
            for index in range(1, len(components)):
                if "/".join(components[:index]) in file_paths:
                    unsafe_members.append(
                        {
                            "member": file_path,
                            "reason": (
                                "requires treating another archived file "
                                "as a directory"
                            ),
                        }
                    )
                    break

        if unsafe_members:
            return None, self._error(
                "unsafe_archive_member",
                "The archive contains unsafe or ambiguous member paths.",
                (
                    "Nothing was extracted because the ZIP contains unsafe "
                    "or ambiguous entries."
                ),
                unsafe_members=unsafe_members[:20],
                unsafe_member_count=len(unsafe_members),
            )
        if file_count > max_files:
            return None, self._error(
                "archive_file_limit_exceeded",
                f"Archive contains {file_count} files; limit is {max_files}.",
                (
                    f"Nothing was extracted because the archive contains "
                    f"{file_count:,} files, above the {max_files:,}-file limit."
                ),
                files_in_archive=file_count,
                max_files=max_files,
            )
        if total_bytes > max_total_bytes:
            return None, self._error(
                "archive_size_limit_exceeded",
                (
                    f"Archive expands to {total_bytes} bytes; limit is "
                    f"{max_total_bytes} bytes."
                ),
                (
                    "Nothing was extracted because the archive's declared "
                    f"uncompressed size is {self._format_bytes(total_bytes)}, "
                    "above the configured "
                    f"{self._format_bytes(max_total_bytes)} limit."
                ),
                total_uncompressed_bytes=total_bytes,
                max_total_bytes=max_total_bytes,
            )
        return {
            "entries": entries,
            "file_count": file_count,
            "total_bytes": total_bytes,
        }, None

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
        source_failure = self._validate_archive_source(zip_path)
        if source_failure is not None:
            return source_failure

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
        try:
            max_files = int(max_files)
            max_total_size_mb = int(max_total_size_mb)
        except (TypeError, ValueError):
            return self._error(
                "invalid_limit",
                "Archive limits must be integers.",
                "max_files and max_total_size_mb must be positive integers.",
                max_files=max_files,
                max_total_size_mb=max_total_size_mb,
            )
        if max_files <= 0 or max_total_size_mb <= 0:
            return self._error(
                "invalid_limit",
                "Archive limits must be greater than zero.",
                "max_files and max_total_size_mb must be greater than zero.",
                max_files=max_files,
                max_total_size_mb=max_total_size_mb,
            )

        absolute_zip = os.path.abspath(str(zip_path).strip())
        absolute_target = os.path.abspath(str(target_path).strip() or ".")
        target_root = Path(absolute_target)
        target_existed = os.path.lexists(absolute_target)
        if target_existed and (
            os.path.islink(absolute_target)
            or not os.path.isdir(absolute_target)
        ):
            return self._error(
                "invalid_target",
                f"Extraction target is not a real directory: {absolute_target}",
                (
                    f"Target '{absolute_target}' must be a directory and "
                    "cannot be a symbolic link."
                ),
                target_path=absolute_target,
            )

        max_total_bytes = max_total_size_mb * 1024 * 1024
        staging_root = None
        created_files = []
        created_directories = []
        replaced_files = 0

        try:
            with zipfile.ZipFile(absolute_zip, "r") as archive:
                validated, validation_failure = self._validated_members(
                    archive,
                    target_root,
                    max_files,
                    max_total_bytes,
                )
                if validation_failure is not None:
                    return validation_failure

                entries = validated["entries"]
                conflicts = (
                    self._destination_conflicts(entries, target_root)
                    if target_existed
                    else []
                )
                if conflicts and not overwrite:
                    return self._error(
                        "destination_conflict",
                        (
                            f"{len(conflicts)} archive destination(s) already "
                            "exist."
                        ),
                        (
                            "Nothing was extracted because existing paths "
                            "would be replaced. Choose an empty target or use "
                            "--overwrite to create a backup first."
                        ),
                        conflicts=conflicts[:20],
                        conflict_count=len(conflicts),
                        target_path=absolute_target,
                    )

                target_parent = target_root.parent
                target_parent.mkdir(parents=True, exist_ok=True)
                staging_root = Path(
                    tempfile.mkdtemp(
                        prefix=".qzx-extract-",
                        dir=str(target_parent),
                    )
                )
                actual_total_bytes = 0
                for member, parts, is_directory in entries:
                    staged_path = staging_root.joinpath(*parts)
                    if is_directory:
                        staged_path.mkdir(parents=True, exist_ok=True)
                        continue
                    staged_path.parent.mkdir(parents=True, exist_ok=True)
                    member_bytes = 0
                    with archive.open(member, "r") as source:
                        with staged_path.open("xb") as destination:
                            while True:
                                chunk = source.read(self._copy_chunk_size)
                                if not chunk:
                                    break
                                member_bytes += len(chunk)
                                actual_total_bytes += len(chunk)
                                if actual_total_bytes > max_total_bytes:
                                    raise ValueError(
                                        "actual extracted data exceeded the "
                                        "configured size limit"
                                    )
                                destination.write(chunk)
                    if member_bytes != member.file_size:
                        raise zipfile.BadZipFile(
                            "member size differs from its ZIP metadata: "
                            f"{member.filename}"
                        )

            if not target_existed:
                os.replace(staging_root, target_root)
                staging_root = None
            else:
                directory_paths = {
                    target_root.joinpath(*parts)
                    for _member, parts, is_directory in entries
                    if is_directory
                }
                for _member, parts, _is_directory in entries:
                    destination = target_root.joinpath(*parts)
                    directory_paths.update(
                        parent
                        for parent in destination.parents
                        if parent != target_root
                        and target_root in parent.parents
                    )
                for directory in sorted(
                    directory_paths,
                    key=lambda item: len(item.parts),
                ):
                    if os.path.lexists(directory):
                        if directory.is_dir():
                            continue
                        if not overwrite:
                            raise FileExistsError(str(directory))
                        self._remove_path(directory)
                    directory.mkdir()
                    created_directories.append(directory)

                for _member, parts, is_directory in entries:
                    if is_directory:
                        continue
                    staged_path = staging_root.joinpath(*parts)
                    destination = target_root.joinpath(*parts)
                    if os.path.lexists(destination):
                        if not overwrite:
                            raise FileExistsError(str(destination))
                        self._remove_path(destination)
                        replaced_files += 1
                    os.replace(staged_path, destination)
                    created_files.append(destination)

            total_bytes = validated["total_bytes"]
            readable_size = self._format_bytes(total_bytes)
            message = (
                f"Extracted {validated['file_count']:,} file(s) from "
                f"'{absolute_zip}' to '{absolute_target}' "
                f"({readable_size})."
            )
            if replaced_files:
                message += (
                    f" Replaced {replaced_files:,} existing file(s) after "
                    "the required safety backup."
                )
            return {
                "success": True,
                "zip_path": absolute_zip,
                "target_path": absolute_target,
                "files_extracted": validated["file_count"],
                "directories_created": len(created_directories),
                "files_replaced": replaced_files,
                "total_bytes_extracted": total_bytes,
                "total_size_readable": readable_size,
                "overwrite": bool(overwrite),
                "limits": {
                    "max_files": max_files,
                    "max_total_size_mb": max_total_size_mb,
                },
                "skipped_traversals": [],
                "message": message,
            }
        except Exception as exc:
            if not overwrite:
                for created_file in reversed(created_files):
                    if os.path.lexists(created_file):
                        self._remove_path(created_file)
                for created_directory in reversed(created_directories):
                    try:
                        created_directory.rmdir()
                    except OSError:
                        pass
            return self._error(
                "extraction_failed",
                f"{type(exc).__name__}: {exc}",
                (
                    "ZIP extraction failed before it could complete: "
                    f"{exc}"
                ),
                zip_path=absolute_zip,
                target_path=absolute_target,
                partial_output_removed=not overwrite,
            )
        finally:
            if staging_root is not None:
                shutil.rmtree(staging_root, ignore_errors=True)
