#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Delete a filesystem entry with preview-first safety controls."""

import os
import shutil
from pathlib import Path

from qzx.core.command_base import CommandBase
from qzx.core.recursive_findfiles_utils import parse_recursive_parameter


class DeleteFileCommand(CommandBase):
    """Delete a file, symlink, or directory after a safety backup."""

    name = "deleteFile"
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
            "command": "qzx deleteFile myfile.txt",
            "description": "Preview deletion of a file (default behavior)",
        },
        {
            "command": "qzx deleteFile mydir --recursive true",
            "description": "Preview recursive deletion of a directory",
        },
        {
            "command": "qzx deleteFile mydir --recursive true --dry_run false --apply",
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
                "message": "Filesystem roots can never be deleted by deleteFile.",
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
        force = self._as_bool(force)
        dry_run = self._as_bool(dry_run)
        apply = self._as_bool(apply)
        allow_unsafe = self._as_bool(allow_unsafe)

        if isinstance(recursive, str):
            parsed_recursive = parse_recursive_parameter(recursive)
            recursive = True if parsed_recursive is None else parsed_recursive

        target_path = Path(target).expanduser()
        resolved_target = target_path.resolve(strict=False)
        exists = os.path.lexists(target_path)
        target_type = (
            "symlink"
            if target_path.is_symlink()
            else "directory"
            if target_path.is_dir()
            else "file"
        )

        details = {
            "target": str(resolved_target),
            "type": target_type,
            "recursive": recursive,
            "force": force,
            "dry_run_mode": dry_run or not apply,
            "apply_requested": apply,
        }

        if not exists:
            return {
                "success": False,
                "error_code": "target_not_found",
                "error": f"Target '{target}' does not exist.",
                "message": "Nothing was deleted because the target does not exist.",
                "details": details,
            }

        if resolved_target.anchor == str(resolved_target):
            return {
                "success": False,
                "error_code": "protected_path",
                "error": f"Refusing to delete filesystem root '{resolved_target}'.",
                "message": "Filesystem roots can never be deleted by deleteFile.",
                "details": details,
            }

        if resolved_target in self._protected_paths() and not allow_unsafe:
            return {
                "success": False,
                "error_code": "protected_path",
                "error": f"Refusing to delete protected path '{resolved_target}'.",
                "message": "Use allow_unsafe=true only after verifying the exact target.",
                "details": details,
            }

        if dry_run or not apply:
            return {
                "success": True,
                "message": (
                    f"Preview only: '{resolved_target}' was not deleted. "
                    "Pass --dry_run false --apply to authorize the operation."
                ),
                "details": details,
            }

        try:
            if target_path.is_symlink() or target_path.is_file():
                target_path.unlink()
            elif target_path.is_dir():
                if recursive is True:
                    shutil.rmtree(target_path)
                elif isinstance(recursive, int) and not isinstance(recursive, bool) and recursive > 0:
                    errors = self._delete_to_depth(target_path, recursive)
                    if errors:
                        return {
                            "success": False,
                            "error_code": "partial_delete",
                            "error": f"Deletion completed with {len(errors)} error(s).",
                            "message": "The requested limited-depth deletion was only partially completed.",
                            "details": {**details, "errors": errors},
                        }
                else:
                    target_path.rmdir()

            return {
                "success": True,
                "message": f"Deleted {target_type} '{resolved_target}'.",
                "details": {**details, "dry_run_mode": False},
            }
        except Exception as exc:
            return {
                "success": False,
                "error_code": "delete_failed",
                "error": str(exc),
                "message": f"Could not delete '{resolved_target}'.",
                "details": details,
            }

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
