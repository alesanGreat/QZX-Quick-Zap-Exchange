#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Move or rename one filesystem entry without partial directory semantics."""

from __future__ import annotations

import os
import shutil
import stat
import uuid
from pathlib import Path

from qzx.commands.file._move_path_workflow import (
    execute_move,
    preflight_move,
)
from qzx.core.command_base import CommandBase
from qzx.core.path_operation_utils import file_sha256


class MovePathCommand(CommandBase):
    """Move one file, symlink, or complete directory."""

    name = "movePath"
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
            "command": "qzx movePath source.txt destination.txt",
            "description": "Move or rename one file",
        },
        {
            "command": "qzx movePath myfile.txt archive/myfile.txt",
            "description": "Move one file into an archive directory",
        },
        {
            "command": "qzx movePath sourcedir destinationdir",
            "description": "Move one complete directory",
        },
        {
            "command": (
                "qzx movePath sourcedir destinationdir --force"
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
            True,
            require_existing_destination=True,
        )
        return None if validation["success"] else validation

    def execute(self, source, destination, force=False):
        """Move a complete filesystem entry and report its committed state."""
        return execute_move(self, source, destination, force)

    def _preflight(
        self,
        source,
        destination,
        force,
        require_existing_destination,
    ):
        return preflight_move(
            self,
            source,
            destination,
            force,
            require_existing_destination,
        )

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
