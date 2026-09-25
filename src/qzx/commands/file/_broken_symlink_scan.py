"""Broken symbolic-link traversal for findBrokenSymlinks."""

from __future__ import annotations

import os


_SKIP_DIRECTORIES = {".git", "node_modules", ".venv", "env"}


def _validate(folder_path):
    absolute = os.path.abspath(folder_path)
    if not os.path.exists(absolute):
        return None, {
            "success": False,
            "error": f"Path '{folder_path}' does not exist.",
            "message": f"Path '{folder_path}' does not exist.",
        }
    if not os.path.isdir(absolute):
        return None, {
            "success": False,
            "error": f"'{folder_path}' is not a directory.",
            "message": f"'{folder_path}' is not a directory.",
        }
    return absolute, None


def _depth(value):
    try:
        return int(value)
    except ValueError:
        return 4


def _link_target(path):
    target = "unknown"
    try:
        target = os.readlink(path)
        if os.name == "nt":
            slash = chr(92)
            unc_prefix = slash * 2 + "?" + slash + "UNC" + slash
            device_prefix = slash * 2 + "?" + slash
            if target.startswith(unc_prefix):
                return slash * 2 + target[len(unc_prefix):]
            if target.startswith(device_prefix):
                return target[len(device_prefix):]
    except Exception:
        pass
    return target


def _broken_link(path, root):
    try:
        if not os.path.islink(path) or os.path.exists(path):
            return None
        return {
            "path": path,
            "relative_path": os.path.relpath(path, root),
            "target": _link_target(path),
        }
    except OSError:
        return None


def _scan(root, depth_limit):
    broken = []
    base_depth = root.count(os.sep)
    for current, directories, files in os.walk(root, topdown=True):
        current_depth = current.count(os.sep) - base_depth
        if current_depth >= depth_limit:
            directories.clear()
            continue
        directories[:] = [
            name for name in directories if name not in _SKIP_DIRECTORIES
        ]
        items = [
            os.path.join(current, name)
            for name in (*directories, *files)
        ]
        for path in items:
            item = _broken_link(path, root)
            if item is not None:
                broken.append(item)
    return broken


def _message(root, broken):
    total = len(broken)
    message = f"Broken symlinks scan completed for '{root}':\n"
    message += f"- Broken symlinks identified: {total}\n"
    if not broken:
        return message + "- Status: Clean. No broken symlinks found."
    message += "\nDetected Broken Symlinks:\n"
    for index, item in enumerate(broken[:10]):
        message += (
            f"  - Index {index}: '{item['relative_path']}' -> "
            f"points to missing '{item['target']}'\n"
        )
    if total > 10:
        message += f"  ... and {total - 10} more.\n"
    return message + (
        "\nNote: You can remove these broken symlinks safely to clean up "
        "path configurations."
    )


def execute_broken_symlink_scan(folder_path=".", max_depth="4"):
    """Scan a directory tree for symbolic links whose targets are missing."""
    root, error = _validate(folder_path)
    if error:
        return error
    try:
        broken = _scan(root, _depth(max_depth))
        return {
            "success": True,
            "scan_path": root,
            "broken_symlinks_count": len(broken),
            "broken_symlinks": broken,
            "message": _message(root, broken),
        }
    except Exception as exc:
        return {
            "success": False,
            "error": str(exc),
            "message": f"Failed to search for broken symlinks: {str(exc)}",
        }
