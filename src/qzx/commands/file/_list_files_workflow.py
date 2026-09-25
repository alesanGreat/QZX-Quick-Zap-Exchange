"""Listing orchestration for listFiles."""

from __future__ import annotations

from fnmatch import fnmatch
import os
import time

from qzx.core.recursive_findfiles_utils import find_files, parse_recursive_parameter


def _entry(command, path, is_directory):
    metadata = os.stat(path)
    return {
        "name": os.path.basename(path),
        "path": path,
        "size": 0 if is_directory else metadata.st_size,
        "size_formatted": "-" if is_directory else command._format_size(metadata.st_size),
        "modified": metadata.st_mtime,
        "modified_formatted": time.strftime(
            "%Y-%m-%d %H:%M:%S", time.localtime(metadata.st_mtime)
        ),
        "is_directory": is_directory,
    }


def _single_file(command, path, pattern, recursive_enabled, depth):
    directory = os.path.dirname(path) or "."
    files = [_entry(command, path, False)] if fnmatch(os.path.basename(path), pattern) else []
    return {
        "success": True,
        "directory": directory,
        "pattern": pattern,
        "recursive": recursive_enabled,
        "recursion_depth": depth,
        "files": files,
        "message": (
            f"Found 1 file matching '{pattern}' in '{directory}'"
            if files
            else f"No files found matching '{pattern}' in '{directory}'"
        ),
    }


def _collect(command, directory, pattern, depth):
    items = []
    search_pattern = os.path.join(directory, pattern)

    def on_file(path):
        items.append(_entry(command, path, False))

    def on_dir(path):
        items.append(_entry(command, path, True))

    for _ in find_files(
        file_path_pattern=search_pattern,
        recursive=depth,
        file_type=None,
        on_file_found=on_file,
        on_dir_found=on_dir,
    ):
        pass
    items.sort(key=lambda item: item["name"].lower())
    return items


def _message(items, directory, pattern, recursive_enabled):
    files = sum(1 for item in items if not item["is_directory"])
    directories = len(items) - files
    if not items:
        message = f"No files found matching '{pattern}' in '{directory}'"
    elif files == 0:
        noun = "directory" if directories == 1 else "directories"
        message = f"Found {directories} {noun} matching '{pattern}' in '{directory}'"
    elif directories == 0:
        suffix = "" if files == 1 else "s"
        message = f"Found {files} file{suffix} matching '{pattern}' in '{directory}'"
    else:
        file_suffix = "" if files == 1 else "s"
        dir_noun = "directory" if directories == 1 else "directories"
        message = (
            f"Found {files} file{file_suffix} and {directories} {dir_noun} "
            f"matching '{pattern}' in '{directory}'"
        )
    if recursive_enabled:
        message += " (including subdirectories)"
    return message


def execute_list_files(command, directory_path=".", pattern="*", recursive=None):
    """List matching files/directories using the centralized finder."""
    try:
        depth = parse_recursive_parameter(recursive)
        recursive_enabled = depth is None or depth > 0
        if not os.path.exists(directory_path):
            message = f"Directory '{directory_path}' not found."
            return {
                "success": False,
                "error": message,
                "error_code": "path_not_found",
                "message": message,
                "details": {"directory": directory_path, "pattern": pattern},
            }
        if os.path.isfile(directory_path):
            return _single_file(
                command, directory_path, pattern, recursive_enabled, depth
            )
        items = _collect(command, directory_path, pattern, depth)
        return {
            "success": True,
            "directory": directory_path,
            "pattern": pattern,
            "recursive": recursive_enabled,
            "recursion_depth": depth,
            "files": items,
            "message": _message(
                items, directory_path, pattern, recursive_enabled
            ),
        }
    except Exception as exc:
        message = f"Error listing files: {exc}"
        return {
            "success": False,
            "error": message,
            "error_code": "list_files_failed",
            "message": message,
            "details": {"directory": directory_path, "pattern": pattern},
        }
