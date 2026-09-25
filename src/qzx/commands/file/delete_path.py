#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Delete a filesystem entry with preview-first safety controls."""

import os
from pathlib import Path

from qzx.commands.file._delete_path_workflow import (
    delete_preflight,
    delete_prepared_path,
    prepare_delete_request,
)
from qzx.core.command_base import CommandBase


class DeletePathCommand(CommandBase):
    """Delete a file, symlink, or directory after a safety backup."""

    name = "deletePath"
    description = "Previews or deletes a file or directory from the filesystem"
    category = "file"
    requires_explicit_approval = True
    backup_target_parameter = "target"

    parameters = [
        {
            "name": "target",
            "description": "Path to the file, symlink, or directory",
            "required": True,
            "type": "str",
        },
        {
            "name": "recursive",
            "description": "Use true/-r for all descendants or a positive integer for limited depth",
            "required": False,
            "default": False,
        },
        {
            "name": "force",
            "description": "Continue a limited-depth deletion after individual errors",
            "required": False,
            "default": False,
            "type": "bool",
        },
        {
            "name": "dry_run",
            "description": "Preview the operation without deleting anything",
            "required": False,
            "default": True,
            "type": "bool",
        },
        {
            "name": "apply",
            "description": "Explicitly authorize deletion; required together with dry_run=false",
            "required": False,
            "default": False,
            "type": "bool",
        },
        {
            "name": "allow_unsafe",
            "description": "Allow deleting protected locations such as the current or home directory",
            "required": False,
            "default": False,
            "type": "bool",
        },
    ]

    examples = [
        {
            "command": "qzx deletePath myfile.txt",
            "description": "Preview deletion of a file (default behavior)",
        },
        {
            "command": "qzx deletePath mydir --recursive true",
            "description": "Preview recursive deletion of a directory",
        },
        {
            "command": "qzx deletePath mydir --recursive true --dry_run false --apply",
            "description": "Back up and delete a directory and all descendants",
        },
    ]

    @staticmethod
    def _as_bool(value):
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}

    @staticmethod
    def _protected_paths():
        protected = {
            Path.cwd().resolve(),
            Path.home().resolve(),
        }
        current = Path.cwd().resolve()
        protected.add(Path(current.anchor).resolve())
        return protected

    def validate_safety_backup_target(self, target, values):
        """Reject impossible or protected targets before creating an archive."""
        target_path = Path(target).expanduser()
        resolved_target = target_path.resolve(strict=False)
        details = {"target": str(resolved_target)}
        if not os.path.lexists(target_path):
            return {
                "success": False,
                "error_code": "target_not_found",
                "error": f"Target '{target}' does not exist.",
                "message": "Nothing was backed up or deleted.",
                "details": details,
            }
        if resolved_target.anchor == str(resolved_target):
            return {
                "success": False,
                "error_code": "protected_path",
                "error": f"Refusing to delete filesystem root '{resolved_target}'.",
                "message": "Filesystem roots can never be deleted by deletePath.",
                "details": details,
            }
        if (
            resolved_target in self._protected_paths()
            and not self._as_bool(values.get("allow_unsafe", False))
        ):
            return {
                "success": False,
                "error_code": "protected_path",
                "error": f"Refusing to delete protected path '{resolved_target}'.",
                "message": "Use allow_unsafe=true only after verifying the exact target.",
                "details": details,
            }
        return None

    def execute(
        self,
        target,
        recursive=False,
        force=False,
        dry_run=True,
        apply=False,
        allow_unsafe=False,
    ):
        request = prepare_delete_request(
            self,
            target,
            recursive,
            force,
            dry_run,
            apply,
            allow_unsafe,
        )
        preflight = delete_preflight(self, request)
        if preflight is not None:
            return preflight
        return delete_prepared_path(self, request)

    @staticmethod
    def _delete_to_depth(target_path, maximum_depth):
        errors = []
        for root, _dirs, files in os.walk(target_path, topdown=False):
            relative = Path(root).relative_to(target_path)
            depth = len(relative.parts)
            if depth > maximum_depth:
                continue
            for filename in files:
                file_path = Path(root) / filename
                try:
                    file_path.unlink()
                except OSError as exc:
                    errors.append({"path": str(file_path), "error": str(exc)})
            try:
                Path(root).rmdir()
            except OSError as exc:
                errors.append({"path": str(root), "error": str(exc)})
        return errors
