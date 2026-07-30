#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Move or rename one filesystem entry without partial directory semantics."""

from __future__ import annotations

import os
import re
import shutil
import stat
import uuid
from pathlib import Path

from qzx.core.command_base import CommandBase
from qzx.core.path_operation_utils import (
    destination_device,
    file_sha256,
    is_filesystem_root,
    same_or_nested_path_relationship,
)


class MoveFileCommand(CommandBase):
    """Move one file, symlink, or complete directory."""

    name = "moveFile"
    description = (
        "Moves or renames one file, symbolic link, or complete directory; "
        "partial directory moves are rejected"
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
            "description": "Path to the new filesystem location",
            "required": True,
            "type": "str",
        },
        {
            "name": "recursive",
            "description": (
                "Compatibility flag for directories: omit it or use -r for "
                "a complete move; finite-depth moves are rejected"
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
            "command": "qzx moveFile source.txt destination.txt",
            "description": "Move or rename one file",
        },
        {
            "command": "qzx moveFile myfile.txt archive/myfile.txt",
            "description": "Move one file into an archive directory",
        },
        {
            "command": "qzx moveFile sourcedir destinationdir",
            "description": "Move one complete directory",
        },
        {
            "command": "qzx moveFile sourcedir destinationdir -r",
            "description": (
                "Move one complete directory using the compatibility flag"
            ),
        },
        {
            "command": (
                "qzx moveFile sourcedir destinationdir -r --force"
            ),
            "description": (
                "Back up and replace an existing destination with a complete "
                "directory"
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
        """Move a complete filesystem entry and report its committed state."""
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
        destination_existed = plan["destination_existed"]

        try:
            destination_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return self._failure(
                "destination_parent_failed",
                (
                    f"Destination parent '{destination_path.parent}' could "
                    f"not be created: {type(exc).__name__}: {exc}"
                ),
                **plan,
            )

        previous_path = None
        if destination_existed:
            previous_path = destination_path.with_name(
                f".{destination_path.name}.qzx-previous-{uuid.uuid4().hex}"
            )
            try:
                os.rename(destination_path, previous_path)
            except OSError as exc:
                return self._failure(
                    "destination_stage_failed",
                    (
                        "The backed-up destination could not be staged for "
                        f"replacement: {type(exc).__name__}: {exc}"
                    ),
                    **plan,
                )

        operation = self._perform_move(
            source_path,
            destination_path,
            plan["same_filesystem"],
        )
        if not operation["success"]:
            recovery = self._recover_failed_replacement(
                source_path,
                destination_path,
                previous_path,
                operation.get("temporary_path"),
            )
            return self._failure(
                "move_failed",
                (
                    f"Move from '{source_path}' to '{destination_path}' "
                    f"failed: {operation['error']}. {recovery['message']}"
                ),
                **plan,
                recovery=recovery,
            )

        cleanup = "not_needed"
        warnings = []
        if previous_path is not None:
            try:
                self._remove_existing_destination(previous_path)
                cleanup = "previous destination removed"
            except OSError as exc:
                cleanup = "previous destination retained"
                warnings.append(
                    (
                        f"Replacement succeeded, but the previous destination "
                        f"remains at '{previous_path}': "
                        f"{type(exc).__name__}: {exc}"
                    )
                )

        entry_type = plan["source_type"]
        message = (
            f"{entry_type.capitalize()} '{source_path}' moved to "
            f"'{destination_path}'."
        )
        result = {
            "success": True,
            "message": message,
            "details": {
                **plan,
                "status": "moved",
                "source_exists_after": os.path.lexists(source_path),
                "destination_exists_after": os.path.lexists(destination_path),
                "verification": operation["verification"],
                "replacement_cleanup": cleanup,
                "retained_previous_path": (
                    str(previous_path)
                    if previous_path is not None
                    and os.path.lexists(previous_path)
                    else None
                ),
            },
        }
        if warnings:
            result["warnings"] = warnings
        return result

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
                f"Source '{source_path}' does not exist, so nothing was moved.",
                **details,
            )
        if is_filesystem_root(source_path) or is_filesystem_root(
            destination_path
        ):
            return self._failure(
                "filesystem_root_protected",
                (
                    "Filesystem roots cannot be used as a move source or "
                    "destination."
                ),
                **details,
            )

        relationship = same_or_nested_path_relationship(
            source_path,
            destination_path,
        )
        details["path_relationship"] = relationship
        if relationship == "same":
            return self._failure(
                "source_equals_destination",
                (
                    "Source and destination identify the same filesystem "
                    "object. Choose a different destination."
                ),
                **details,
            )
        if relationship == "destination_within_source":
            return self._failure(
                "destination_within_source",
                (
                    "Destination is inside the source. Moving a directory into "
                    "itself is not a valid complete move."
                ),
                **details,
            )
        if relationship == "source_within_destination":
            return self._failure(
                "source_within_destination",
                (
                    "Source is inside the destination. Replacing that "
                    "destination could delete the source before the move."
                ),
                **details,
            )

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
                    "Move accepts only regular files, symbolic links, and "
                    "directories; special filesystem entries are rejected."
                ),
                **details,
            )
        details["source_type"] = source_type

        recursion = self._normalize_recursion(recursive)
        if not recursion["success"]:
            return self._failure(
                recursion["error_code"],
                recursion["message"],
                **details,
            )
        details["recursive"] = recursion["value"]
        if source_type == "directory" and recursion["value"] != "complete":
            return self._failure(
                "partial_directory_move_unsupported",
                (
                    "Finite-depth directory moves are not safe complete moves. "
                    "Omit recursive or use -r to move the entire directory; "
                    "use copyFile for a deliberate depth-limited copy."
                ),
                **details,
            )
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

        source_device = os.lstat(source_path).st_dev
        try:
            target_device = destination_device(destination_path)
        except OSError as exc:
            return self._failure(
                "destination_device_unknown",
                str(exc),
                **details,
            )
        same_filesystem = source_device == target_device
        details["same_filesystem"] = same_filesystem
        if source_type == "directory" and not same_filesystem:
            return self._failure(
                "cross_filesystem_directory_move_unsupported",
                (
                    "QZX refuses cross-filesystem directory moves because "
                    "they can leave a partially copied and partially deleted "
                    "tree. Copy and verify the directory first, then delete "
                    "the source as a separate approved operation."
                ),
                **details,
            )

        return {"success": True, "details": details}

    def _perform_move(self, source, destination, same_filesystem):
        if same_filesystem:
            try:
                os.rename(source, destination)
            except OSError as exc:
                return {
                    "success": False,
                    "error": f"{type(exc).__name__}: {exc}",
                    "verification": "not_completed",
                }
            return {
                "success": True,
                "verification": "same-filesystem rename committed",
            }

        temporary = destination.with_name(
            f".{destination.name}.qzx-move-stage-{uuid.uuid4().hex}"
        )
        try:
            source_mode = os.lstat(source).st_mode
            if stat.S_ISLNK(source_mode):
                link_target = os.readlink(source)
                os.symlink(
                    link_target,
                    temporary,
                    target_is_directory=os.path.isdir(source),
                )
                if os.readlink(temporary) != link_target:
                    raise OSError("staged symbolic-link target did not match")
                verification = "symbolic-link target matched"
            else:
                source_size = os.path.getsize(source)
                source_digest = file_sha256(source)
                shutil.copy2(source, temporary)
                if (
                    os.path.getsize(temporary) != source_size
                    or file_sha256(temporary) != source_digest
                ):
                    raise OSError("staged file failed size or SHA-256 verification")
                verification = "size and SHA-256 matched"
            os.replace(temporary, destination)
            os.unlink(source)
            return {
                "success": True,
                "verification": verification,
            }
        except OSError as exc:
            return {
                "success": False,
                "error": f"{type(exc).__name__}: {exc}",
                "verification": "failed",
                "temporary_path": str(temporary),
            }

    def _recover_failed_replacement(
        self,
        source,
        destination,
        previous,
        temporary,
    ):
        errors = []
        temporary_path = Path(temporary) if temporary else None
        if temporary_path is not None and os.path.lexists(temporary_path):
            try:
                self._remove_existing_destination(temporary_path)
            except OSError as exc:
                errors.append(
                    f"could not remove temporary entry '{temporary_path}': {exc}"
                )

        if os.path.lexists(destination) and os.path.lexists(source):
            try:
                self._remove_existing_destination(destination)
            except OSError as exc:
                errors.append(
                    f"could not remove uncommitted destination: {exc}"
                )

        restored = previous is None
        if previous is not None:
            if not os.path.lexists(destination):
                try:
                    os.rename(previous, destination)
                    restored = True
                except OSError as exc:
                    errors.append(
                        f"could not restore previous destination: {exc}"
                    )
            else:
                errors.append(
                    (
                        f"previous destination remains staged at '{previous}' "
                        "because the destination path is occupied"
                    )
                )

        source_preserved = os.path.lexists(source)
        success = restored and source_preserved and not errors
        return {
            "success": success,
            "source_preserved": source_preserved,
            "previous_destination_restored": restored,
            "errors": errors,
            "message": (
                "The source and previous destination were preserved."
                if success
                else "Manual recovery may be required; inspect recovery details."
            ),
        }

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
