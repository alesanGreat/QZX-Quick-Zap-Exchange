#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Move or rename one filesystem entry without partial directory semantics."""

from __future__ import annotations

import os
import shutil

from qzx.commands.file._move_path_transfer import (
    perform_move,
    recover_failed_replacement,
)
from qzx.commands.file._move_path_workflow import (
    execute_move,
    preflight_move,
)
from qzx.core.command_base import CommandBase


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
        return perform_move(source, destination, same_filesystem)

    def _recover_failed_replacement(
        self,
        source,
        destination,
        previous,
        temporary,
    ):
        return recover_failed_replacement(
            self,
            source,
            destination,
            previous,
            temporary,
        )

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
