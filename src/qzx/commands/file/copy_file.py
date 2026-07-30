#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Copy a filesystem entry without unsafe source/destination overlap."""

from __future__ import annotations

import os
import re
import shutil
import stat
from pathlib import Path

from qzx.core.command_base import CommandBase
from qzx.core.path_operation_utils import (
    file_sha256,
    is_filesystem_root,
    same_or_nested_path_relationship,
)


class CopyFileCommand(CommandBase):
    """Copy one file, symlink, or directory to a separate path."""

    name = "copyFile"
    description = (
        "Copies one file, symbolic link, or directory to a separate "
        "destination with explicit depth and replacement behavior"
    )
    category = "file"
    requires_explicit_approval = True
    approval_when_parameter = "force"
    backup_target_parameter = "destination"

    parameters = [
        {
            "name": "source",
            "description": "Path to the source file, symlink, or directory",
            "required": True,
            "type": "str",
        },
        {
            "name": "destination",
            "description": "Path to the separate destination",
            "required": True,
            "type": "str",
        },
        {
            "name": "recursive",
            "description": (
                "For directories: omit or use -r to copy everything; use "
                "-rN for at most N levels; false/0 creates only the root"
            ),
            "required": False,
            "default": None,
        },
        {
            "name": "force",
            "description": (
                "Replace an existing destination after a safety backup"
            ),
            "required": False,
            "default": False,
            "type": "bool",
        },
    ]

    examples = [
        {
            "command": "qzx copyFile source.txt destination.txt",
            "description": "Copy one regular file and verify it with SHA-256",
        },
        {
            "command": "qzx copyFile myfile.txt backup/myfile.txt",
            "description": "Copy one file into a backup directory",
        },
        {
            "command": "qzx copyFile sourcedir destinationdir -r",
            "description": "Copy a complete directory and preserve symlinks",
        },
        {
            "command": "qzx copyFile sourcedir destinationdir -r2",
            "description": "Copy a directory through two levels",
        },
        {
            "command": (
                "qzx copyFile sourcedir destinationdir -r --force"
            ),
            "description": (
                "Back up and replace an existing destination with a complete "
                "copy"
            ),
        },
    ]

    def validate_safety_backup_target(self, target, values):
        """Reject unsafe forced replacements before creating their backup."""
        validation = self._preflight(
            values.get("source"),
            target,
            values.get("recursive"),
            True,
            require_existing_destination=True,
        )
        return None if validation["success"] else validation

    def execute(self, source, destination, recursive=None, force=False):
        """Copy one entry after validating its complete path relationship."""
        force_value = self._parse_bool(force)
        if force_value is None:
            return self._failure(
                "invalid_boolean",
                f"force must be true or false; got {force!r}.",
                source=source,
                destination=destination,
            )
        validation = self._preflight(
            source,
            destination,
            recursive,
            force_value,
            require_existing_destination=False,
        )
        if not validation["success"]:
            return validation
        plan = validation["details"]
        source_path = Path(plan["source"])
        destination_path = Path(plan["destination"])

        try:
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            if plan["destination_existed"]:
                self._remove_existing_destination(destination_path)
            operation = self._copy_entry(
                source_path,
                destination_path,
                plan["source_type"],
                plan["recursive"],
            )
        except OSError as exc:
            return self._failure(
                "copy_failed",
                (
                    f"Copy from '{source_path}' to '{destination_path}' "
                    f"failed: {type(exc).__name__}: {exc}"
                ),
                **plan,
                destination_exists_after=os.path.lexists(destination_path),
            )

        return {
            "success": True,
            "message": (
                f"{plan['source_type'].capitalize()} '{source_path}' copied "
                f"to '{destination_path}'."
            ),
            "details": {
                **plan,
                "status": "copied",
                "source_exists_after": os.path.lexists(source_path),
                "destination_exists_after": os.path.lexists(destination_path),
                **operation,
            },
        }

    def _preflight(
        self,
        source,
        destination,
        recursive,
        force,
        require_existing_destination,
    ):
        source_path = Path(os.path.abspath(os.fspath(source)))
        destination_path = Path(os.path.abspath(os.fspath(destination)))
        details = {
            "source": str(source_path),
            "destination": str(destination_path),
            "force": bool(force),
        }
        if not os.path.lexists(source_path):
            return self._failure(
                "source_missing",
                f"Source '{source_path}' does not exist, so nothing was copied.",
                **details,
            )
        if is_filesystem_root(source_path) or is_filesystem_root(
            destination_path
        ):
            return self._failure(
                "filesystem_root_protected",
                (
                    "Filesystem roots cannot be used as a copy source or "
                    "destination."
                ),
                **details,
            )

        relationship = same_or_nested_path_relationship(
            source_path,
            destination_path,
        )
        details["path_relationship"] = relationship
        relationship_failures = {
            "same": (
                "source_equals_destination",
                (
                    "Source and destination identify the same filesystem "
                    "object. Choose a different destination."
                ),
            ),
            "destination_within_source": (
                "destination_within_source",
                (
                    "Destination is inside the source. Copying a directory "
                    "into itself can recurse indefinitely and is blocked."
                ),
            ),
            "source_within_destination": (
                "source_within_destination",
                (
                    "Source is inside the destination. Replacing that "
                    "destination could delete the source before copying it."
                ),
            ),
        }
        if relationship in relationship_failures:
            error_code, message = relationship_failures[relationship]
            return self._failure(error_code, message, **details)

        mode = os.lstat(source_path).st_mode
        if stat.S_ISLNK(mode):
            source_type = "symbolic link"
        elif stat.S_ISDIR(mode):
            source_type = "directory"
        elif stat.S_ISREG(mode):
            source_type = "file"
        else:
            return self._failure(
                "unsupported_source_type",
                (
                    "Copy accepts only regular files, symbolic links, and "
                    "directories; special filesystem entries are rejected."
                ),
                **details,
            )
        details["source_type"] = source_type
        if source_type == "directory":
            unsafe_entry = self._first_unsafe_directory_entry(source_path)
            if unsafe_entry is not None:
                return self._failure(
                    "unsupported_source_entry",
                    (
                        f"Directory contains unsupported special entry "
                        f"'{unsafe_entry}'. Copy accepts only directories, "
                        "regular files, and symbolic links."
                    ),
                    **details,
                    unsupported_entry=str(unsafe_entry),
                )

        recursion = self._normalize_recursion(recursive)
        if not recursion["success"]:
            return self._failure(
                recursion["error_code"],
                recursion["message"],
                **details,
            )
        details["recursive"] = recursion["value"]
        if source_type != "directory" and recursive is not None:
            return self._failure(
                "recursive_not_applicable",
                "recursive applies only to directory sources.",
                **details,
            )

        destination_existed = os.path.lexists(destination_path)
        details["destination_existed"] = destination_existed
        if require_existing_destination and not destination_existed:
            return self._failure(
                "overwrite_target_missing",
                (
                    f"Destination '{destination_path}' does not exist. Omit "
                    "--force to create it without an unnecessary safety backup."
                ),
                **details,
            )
        if destination_existed and not force:
            return self._failure(
                "destination_exists",
                (
                    f"Destination '{destination_path}' already exists. Use "
                    "--force to replace it after a safety backup."
                ),
                **details,
            )
        return {"success": True, "details": details}

    def _copy_entry(self, source, destination, source_type, recursion):
        if source_type == "symbolic link":
            link_target = os.readlink(source)
            os.symlink(
                link_target,
                destination,
                target_is_directory=os.path.isdir(source),
            )
            if os.readlink(destination) != link_target:
                raise OSError("copied symbolic-link target did not match")
            return {"verification": "symbolic-link target matched"}

        if source_type == "file":
            source_size = os.path.getsize(source)
            source_digest = file_sha256(source)
            shutil.copy2(source, destination)
            destination_size = os.path.getsize(destination)
            destination_digest = file_sha256(destination)
            if (
                source_size != destination_size
                or source_digest != destination_digest
            ):
                raise OSError("copied file failed size or SHA-256 verification")
            return {
                "bytes": source_size,
                "human_size": self._format_bytes(float(source_size)),
                "sha256": source_digest,
                "verification": "size and SHA-256 matched",
            }

        if recursion == "complete":
            shutil.copytree(source, destination, symlinks=True)
            return {"verification": "complete directory copy committed"}

        destination.mkdir(parents=True, exist_ok=True)
        copied_files = self._copy_directory_to_depth(
            source,
            destination,
            recursion,
        )
        return {
            "files_copied": copied_files,
            "verification": (
                f"depth-limited directory copy through {recursion} levels"
            ),
        }

    def _copy_directory_to_depth(
        self,
        source,
        destination,
        maximum_depth,
        current_depth=0,
    ):
        copied_files = 0
        for item in sorted(source.iterdir(), key=lambda entry: entry.name):
            target = destination / item.name
            if item.is_dir() and not item.is_symlink():
                if current_depth < maximum_depth:
                    target.mkdir()
                    copied_files += self._copy_directory_to_depth(
                        item,
                        target,
                        maximum_depth,
                        current_depth + 1,
                    )
            else:
                shutil.copy2(item, target, follow_symlinks=False)
                copied_files += 1
        return copied_files

    @staticmethod
    def _first_unsafe_directory_entry(source):
        for root, directory_names, file_names in os.walk(
            source,
            topdown=True,
            followlinks=False,
        ):
            root_path = Path(root)
            for name in [*directory_names, *file_names]:
                entry = root_path / name
                mode = os.lstat(entry).st_mode
                if (
                    stat.S_ISDIR(mode)
                    or stat.S_ISREG(mode)
                    or stat.S_ISLNK(mode)
                ):
                    continue
                return entry.relative_to(source)
        return None

    @staticmethod
    def _normalize_recursion(value):
        if value is None or value is True:
            return {"success": True, "value": "complete"}
        if value is False:
            return {"success": True, "value": 0}
        if isinstance(value, int):
            if value < 0:
                return {
                    "success": False,
                    "error_code": "invalid_recursive",
                    "message": "recursive depth must not be negative.",
                }
            return {"success": True, "value": value}
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"-r", "--recursive", "true", "yes", "1"}:
                return {"success": True, "value": "complete"}
            if normalized in {"false", "no", "0"}:
                return {"success": True, "value": 0}
            match = re.fullmatch(r"(?:-r|--recursive)(\d+)", normalized)
            if match:
                return {"success": True, "value": int(match.group(1))}
        return {
            "success": False,
            "error_code": "invalid_recursive",
            "message": (
                "recursive must be omitted, -r/--recursive, or a finite "
                "depth flag such as -r2."
            ),
        }

    @staticmethod
    def _remove_existing_destination(destination):
        if os.path.isdir(destination) and not os.path.islink(destination):
            shutil.rmtree(destination)
        else:
            os.unlink(destination)

    @staticmethod
    def _failure(error_code, message, **details):
        return {
            "success": False,
            "error_code": error_code,
            "error": message,
            "message": message,
            "details": details,
        }
