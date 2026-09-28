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
        return max(0, int(value))
    except (TypeError, ValueError):
        return 4


def _link_target(path, read_link=os.readlink):
    target = read_link(path)
    if os.name == "nt":
        slash = chr(92)
        unc_prefix = slash * 2 + "?" + slash + "UNC" + slash
        device_prefix = slash * 2 + "?" + slash
        if target.startswith(unc_prefix):
            return slash * 2 + target[len(unc_prefix):]
        if target.startswith(device_prefix):
            return target[len(device_prefix):]
    return target


def _is_junction(path):
    checker = getattr(os.path, "isjunction", None)
    return bool(checker and checker(path))


def _scan_issue(path, root, operation, error):
    try:
        relative = os.path.relpath(path, root)
    except (TypeError, ValueError):
        relative = str(path)
    return {
        "path": relative,
        "operation": operation,
        "error": f"{type(error).__name__}: {error}",
    }


def _broken_link(
    path,
    root,
    *,
    is_link=os.path.islink,
    is_junction=_is_junction,
    stat_path=os.stat,
    read_link=os.readlink,
):
    try:
        if not (is_link(path) or is_junction(path)):
            return None, None
        try:
            stat_path(path)
        except FileNotFoundError:
            try:
                target = _link_target(path, read_link=read_link)
                issue = None
            except OSError as exc:
                target = "unknown"
                issue = _scan_issue(path, root, "read_link_target", exc)
            return {
                "path": path,
                "relative_path": os.path.relpath(path, root),
                "target": target,
            }, issue
        return None, None
    except OSError as exc:
        return None, _scan_issue(path, root, "inspect_link", exc)


def _scan(root, depth_limit):
    broken = []
    scan_issues = []

    def on_walk_error(error):
        path = getattr(error, "filename", None) or root
        scan_issues.append(_scan_issue(path, root, "walk_directory", error))

    base_depth = root.count(os.sep)
    for current, directories, files in os.walk(
        root,
        topdown=True,
        onerror=on_walk_error,
    ):
        current_depth = current.count(os.sep) - base_depth
        visible_directories = [
            name for name in directories if name not in _SKIP_DIRECTORIES
        ]
        if current_depth >= depth_limit:
            directories.clear()
        else:
            directories[:] = visible_directories
        items = [
            os.path.join(current, name)
            for name in (*visible_directories, *files)
        ]
        for path in items:
            item, issue = _broken_link(path, root)
            if item is not None:
                broken.append(item)
            if issue is not None:
                scan_issues.append(issue)
    return broken, scan_issues


def _message(root, broken, scan_issues):
    total = len(broken)
    message = f"Broken symlinks scan completed for '{root}':\n"
    message += f"- Broken symlinks identified: {total}\n"
    message += f"- Scan issues: {len(scan_issues)}\n"
    if not broken:
        if scan_issues:
            return message + (
                "- Status: Incomplete. Some paths could not be inspected; "
                "the scan cannot claim the tree is clean."
            )
        return message + "- Status: Clean. No broken symlinks found."
    message += "\nDetected Broken Symlinks:\n"
    for index, item in enumerate(broken[:10]):
        message += (
            f"  - Index {index}: '{item['relative_path']}' -> "
            f"points to missing '{item['target']}'\n"
        )
    if total > 10:
        message += f"  ... and {total - 10} more.\n"
    if scan_issues:
        return message + (
            "\nStatus: Incomplete. Broken links were found, but some paths "
            "could not be inspected."
        )
    return message + (
        "\nNote: You can remove these broken symlinks safely to clean up "
        "path configurations."
    )


def _build_result(root, broken, scan_issues):
    complete = not scan_issues
    result = {
        "success": complete,
        "analysis_complete": complete,
        "scan_path": root,
        "broken_symlinks_count": len(broken),
        "broken_symlinks": broken,
        "scan_issues": scan_issues,
        "message": _message(root, broken, scan_issues),
    }
    if not complete:
        result["error_code"] = "symlink_scan_incomplete"
        result["error"] = (
            f"Could not inspect {len(scan_issues)} path(s) completely."
        )
    return result


def execute_broken_symlink_scan(folder_path=".", max_depth="4"):
    """Scan a directory tree for symbolic links whose targets are missing."""
    root, error = _validate(folder_path)
    if error:
        return error
    try:
        broken, scan_issues = _scan(root, _depth(max_depth))
        return _build_result(root, broken, scan_issues)
    except Exception as exc:
        return {
            "success": False,
            "analysis_complete": False,
            "error": str(exc),
            "message": f"Failed to search for broken symlinks: {str(exc)}",
        }
