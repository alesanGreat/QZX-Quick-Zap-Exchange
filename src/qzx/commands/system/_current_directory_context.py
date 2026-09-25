"""Result assembly and directory context for getCurrentDirectory."""

from __future__ import annotations

import os
import shutil
from pathlib import Path


def same_path(first, second):
    """Compare absolute paths without resolving either path."""
    return os.path.normcase(os.path.abspath(first)) == os.path.normcase(
        os.path.abspath(second)
    )


def home_relative_path(directory, home_directory):
    """Return a home-relative display path only when inside home."""
    try:
        common = os.path.commonpath(
            [os.path.abspath(directory), os.path.abspath(home_directory)]
        )
    except ValueError:
        return None
    if not same_path(common, home_directory):
        return None
    relative = os.path.relpath(directory, home_directory)
    return "~" if relative == "." else "~{}{}".format(os.path.sep, relative)


def directory_details(directory, home_directory, format_bytes, iso_timestamp):
    """Collect cheap directory and containing-filesystem context."""
    directory_stat = os.stat(directory)
    disk = shutil.disk_usage(directory)
    used_percent = round((disk.used / disk.total) * 100, 2) if disk.total else 0
    return {
        "directory": {
            "modified_at": iso_timestamp(directory_stat.st_mtime),
            "readable": os.access(directory, os.R_OK),
            "writable": os.access(directory, os.W_OK),
            "searchable": os.access(directory, os.X_OK),
            "is_home_directory": same_path(directory, home_directory),
            "is_filesystem_root": same_path(
                directory, Path(directory).anchor or os.path.sep
            ),
        },
        "filesystem": {
            "total_bytes": disk.total,
            "total_formatted": format_bytes(disk.total),
            "used_bytes": disk.used,
            "used_formatted": format_bytes(disk.used),
            "free_bytes": disk.free,
            "free_formatted": format_bytes(disk.free),
            "used_percent": used_percent,
        },
    }


def invalid_limit_result(limit):
    return {
        "success": False,
        "error_code": "invalid_limit",
        "error": "limit must be between 1 and 100",
        "message": (
            "Could not inspect the current directory: --limit must be "
            "an integer between 1 and 100."
        ),
        "details": {"received_limit": limit, "minimum": 1, "maximum": 100},
    }


def _base_message(command, displayed, contents):
    message = (
        "Current directory: {}. At this level: {}, {}, {}, {} ({} total)."
    ).format(
        displayed,
        command._counted_noun(contents["file_count"], "file"),
        command._counted_noun(contents["directory_count"], "directory", "directories"),
        command._counted_noun(contents["symlink_count"], "symbolic link"),
        command._counted_noun(contents["other_count"], "other entry", "other entries"),
        contents["entry_count"],
    )
    return message


def _base_result(command, current_dir, full, size, details, limit):
    parent = os.path.dirname(current_dir)
    name = os.path.basename(os.path.normpath(current_dir)) or current_dir
    home = os.path.expanduser("~")
    relative = command._home_relative_path(current_dir, home)
    displayed = current_dir if full else name
    contents = command._scan_current_level(current_dir, details, limit)
    message = _base_message(command, displayed, contents)
    if full and relative:
        message += " Home-relative path: {}.".format(relative)
    elif not full:
        message += " Full path: {}.".format(current_dir)
    result = {
        "success": True,
        "current_dir": current_dir,
        "full_path": bool(full),
        "displayed_path": displayed,
        "directory_name": name,
        "parent_directory": parent,
        "contents": contents,
        "analysis_requested": {
            "size": bool(size),
            "details": bool(details),
            "list_limit": limit,
        },
        "message": message,
    }
    if relative:
        result["home_relative_path"] = relative
    return result, home


def _add_recursive(command, result, current_dir, details, limit):
    recursive = command._scan_recursive(current_dir, details, limit)
    result["recursive_analysis"] = recursive
    result["message"] += (
        " Recursive total: {} across {} files and {} directories."
    ).format(
        recursive["total_size_formatted"],
        recursive["file_count"],
        recursive["directory_count"],
    )
    if not recursive["scan_complete"]:
        result["message"] += " The recursive scan was partial due to {} errors.".format(
            recursive["scan_error_count"]
        )


def _add_warning(result):
    if result["contents"]["scan_complete"]:
        return
    result.setdefault("warnings", []).append(
        {
            "code": "current_level_scan_partial",
            "message": (
                "Some entries could not be inspected; current-level counts "
                "may be incomplete."
            ),
        }
    )


def execute_current_directory(command, full=True, size=False, details=False, limit=10):
    """Run the public getCurrentDirectory workflow."""
    if not 1 <= limit <= 100:
        return invalid_limit_result(limit)
    try:
        current_dir = os.getcwd()
        result, home = _base_result(
            command, current_dir, full, size, details, limit
        )
        if size or details:
            _add_recursive(command, result, current_dir, details, limit)
        if details:
            result.update(command._directory_details(current_dir, home))
        _add_warning(result)
        return result
    except Exception as exc:
        return {
            "success": False,
            "error_code": "current_directory_inspection_failed",
            "error": "{}: {}".format(type(exc).__name__, str(exc)),
            "message": (
                "Failed to retrieve current directory information: {}"
            ).format(str(exc)),
        }
