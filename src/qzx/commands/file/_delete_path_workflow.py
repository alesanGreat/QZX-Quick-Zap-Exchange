"""Prepared deletePath request, preflight, and mutation workflow."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from qzx.core.recursive_findfiles_utils import parse_recursive_parameter


def prepare_delete_request(
    command,
    target,
    recursive,
    force,
    dry_run,
    apply,
    allow_unsafe,
):
    """Normalize arguments and inspect the target once."""
    force = command._as_bool(force)
    dry_run = command._as_bool(dry_run)
    apply = command._as_bool(apply)
    allow_unsafe = command._as_bool(allow_unsafe)
    if isinstance(recursive, str):
        parsed_recursive = parse_recursive_parameter(recursive)
        recursive = True if parsed_recursive is None else parsed_recursive

    target_path = Path(target).expanduser()
    resolved_target = target_path.resolve(strict=False)
    target_type = (
        "symlink"
        if target_path.is_symlink()
        else "directory"
        if target_path.is_dir()
        else "file"
    )
    return {
        "target": target,
        "target_path": target_path,
        "resolved_target": resolved_target,
        "exists": os.path.lexists(target_path),
        "target_type": target_type,
        "recursive": recursive,
        "allow_unsafe": allow_unsafe,
        "details": {
            "target": str(resolved_target),
            "type": target_type,
            "recursive": recursive,
            "force": force,
            "dry_run_mode": dry_run or not apply,
            "apply_requested": apply,
        },
    }


def delete_preflight(command, request):
    """Return a refusal/preview result, or None when mutation may proceed."""
    details = request["details"]
    resolved_target = request["resolved_target"]
    if not request["exists"]:
        return {
            "success": False,
            "error_code": "target_not_found",
            "error": f"Target '{request['target']}' does not exist.",
            "message": "Nothing was deleted because the target does not exist.",
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
        resolved_target in command._protected_paths()
        and not request["allow_unsafe"]
    ):
        return {
            "success": False,
            "error_code": "protected_path",
            "error": f"Refusing to delete protected path '{resolved_target}'.",
            "message": "Use allow_unsafe=true only after verifying the exact target.",
            "details": details,
        }
    if details["dry_run_mode"]:
        return {
            "success": True,
            "message": (
                f"Preview only: '{resolved_target}' was not deleted. "
                "Pass --dry_run false --apply to authorize the operation."
            ),
            "details": details,
        }
    return None


def delete_prepared_path(command, request):
    """Perform the authorized deletion and preserve existing result contracts."""
    target_path = request["target_path"]
    resolved_target = request["resolved_target"]
    target_type = request["target_type"]
    recursive = request["recursive"]
    details = request["details"]
    try:
        if target_path.is_symlink() or target_path.is_file():
            target_path.unlink()
        elif target_path.is_dir():
            partial = _delete_directory(command, target_path, recursive)
            if partial is not None:
                return {
                    "success": False,
                    "error_code": "partial_delete",
                    "error": f"Deletion completed with {len(partial)} error(s).",
                    "message": (
                        "The requested limited-depth deletion was only partially "
                        "completed."
                    ),
                    "details": {**details, "errors": partial},
                }
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


def _delete_directory(command, target_path, recursive):
    if recursive is True:
        shutil.rmtree(target_path)
        return None
    if isinstance(recursive, int) and not isinstance(recursive, bool) and recursive > 0:
        errors = command._delete_to_depth(target_path, recursive)
        return errors or None
    target_path.rmdir()
    return None
