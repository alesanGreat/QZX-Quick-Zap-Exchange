"""Semantic workflow for changePermissions."""

from __future__ import annotations

import os
import stat
import sys

from qzx.core.recursive_findfiles_utils import parse_recursive_parameter


def change_permissions(command, path, mode, recursive=False):
    """Apply a validated permission mode to one path or a recursive tree."""
    try:
        recursive = _normalized_recursion(recursive)
        if not os.path.exists(path):
            return {
                "success": False,
                "error": f"Path '{path}' does not exist",
            }

        normalized_mode, failure = _normalized_mode(mode)
        if failure is not None:
            return failure

        failure = _restrictive_mode_failure(path, normalized_mode)
        if failure is not None:
            return failure

        result = _base_result(path, normalized_mode, recursive)
        if os.path.isfile(path):
            return _apply_single(command, path, normalized_mode, result)
        if os.path.isdir(path) and recursive == 0:
            return _apply_single(command, path, normalized_mode, result)
        if os.path.isdir(path):
            return _apply_recursive(
                command,
                path,
                normalized_mode,
                recursive,
                result,
            )
        return result
    except Exception as exc:
        return {
            "success": False,
            "path": path,
            "error": str(exc),
        }


def _normalized_recursion(recursive):
    recursive_flags = ["-r", "-R", "--recursive"]
    if recursive is False and any(flag in sys.argv for flag in recursive_flags):
        recursive = True
    return parse_recursive_parameter(recursive)


def _normalized_mode(mode):
    if not isinstance(mode, str):
        return mode, None
    if mode.isdigit():
        return int(mode, 8), None
    return None, {
        "success": False,
        "error": (
            f"Symbolic mode '{mode}' is not supported yet. "
            "Use numeric octal mode (e.g., 755)."
        ),
    }


def _restrictive_mode_failure(path, mode):
    required_owner_bits = stat.S_IRUSR | stat.S_IWUSR
    if os.path.isdir(path):
        required_owner_bits |= stat.S_IXUSR
    if mode & required_owner_bits == required_owner_bits:
        return None
    return {
        "success": False,
        "path": os.path.abspath(path),
        "mode": oct(mode)[2:],
        "error_code": "restrictive_permissions_blocked",
        "error": (
            "QZX refuses permission modes that can remove the owner's required "
            "read/write access or directory traversal."
        ),
    }


def _base_result(path, mode, recursive):
    return {
        "path": os.path.abspath(path),
        "type": "directory" if os.path.isdir(path) else "file",
        "mode": oct(mode)[2:],
        "recursive": recursive,
        "success": True,
    }


def _apply_single(command, path, mode, result):
    command._chmod(path, mode)
    result["message"] = (
        f"Changed permissions of '{path}' to {result['mode']}"
    )
    return result


def _apply_recursive(command, path, mode, recursive, result):
    state = {"count": 0}
    command._chmod(path, mode)
    state["count"] += 1

    def change_entry(entry_path):
        try:
            command._chmod(entry_path, mode)
            state["count"] += 1
        except Exception as exc:
            result.setdefault("warnings", []).append(
                f"Failed to change permissions for '{entry_path}': {str(exc)}"
            )
        return True

    for _ in command._finder(
        file_path_pattern=path,
        recursive=recursive,
        file_type=None,
        on_file_found=change_entry,
        on_dir_found=change_entry,
    ):
        pass

    result["message"] = (
        f"Changed permissions of '{path}' and its contents to "
        f"{result['mode']} (recursive)"
    )
    result["items_modified"] = state["count"]
    return result
