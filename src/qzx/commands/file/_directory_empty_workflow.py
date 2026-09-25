"""Stable streaming emptiness workflow for isDirectoryEmpty."""

from __future__ import annotations

from qzx.core.file_content_analysis import (
    DirectoryChangedDuringScanError,
    directory_fingerprint,
    normalize_boolean,
    validate_directory,
)


def _normalize(command, include_hidden, follow_symlinks):
    include_hidden, error = normalize_boolean(
        include_hidden,
        field="include_hidden",
        command_base=command,
    )
    if error is not None:
        return None, None, error
    follow_links, error = normalize_boolean(
        follow_symlinks,
        field="follow_symlinks",
        command_base=command,
    )
    return include_hidden, follow_links, error


def _consume_entry(command, entry, include_hidden, counts, error_samples):
    counts["total_entries"] += 1
    hidden = False
    try:
        hidden = bool(command._hidden_predicate(entry))
    except (OSError, RuntimeError, ValueError) as exc:
        command._record_scan_error(
            counts, error_samples, entry.path, "hidden_attribute", exc
        )
    if hidden and not include_hidden:
        counts["ignored_hidden_entries"] += 1
        return
    counts["considered_entries"] += 1
    try:
        entry_type = command._entry_type(entry)
    except OSError as exc:
        counts["unavailable_count"] += 1
        command._record_scan_error(
            counts, error_samples, entry.path, "entry_type", exc
        )
        return
    counts[f"{entry_type}_count"] += 1


def _scan(command, target, include_hidden):
    counts = command._empty_counts()
    error_samples = []
    initial = directory_fingerprint(target.analyzed_path)
    if initial != target.fingerprint:
        raise DirectoryChangedDuringScanError(
            "The directory changed between validation and enumeration."
        )
    with command._scandir(target.analyzed_path) as entries:
        for entry in entries:
            _consume_entry(
                command, entry, include_hidden, counts, error_samples
            )
    final = directory_fingerprint(target.analyzed_path)
    if final != initial:
        raise DirectoryChangedDuringScanError(
            "The directory changed while entries were being enumerated."
        )
    return counts, error_samples


def _scan_failure(target, counts, error):
    return {
        "success": False,
        "error_code": "directory_scan_failed",
        "error": f"{type(error).__name__}: {error}",
        "message": f"QZX could not scan directory '{target.analyzed_path}'.",
        "directory_path": str(target.absolute_path),
        "analyzed_path": str(target.analyzed_path),
        "details": {
            "target": target.evidence(),
            **counts,
            "scan_complete": False,
            "symbolic_links_followed_inside_directory": False,
        },
    }


def _details(target, counts, error_samples, include_hidden):
    details = {
        "target": target.evidence(),
        **counts,
        "scan_complete": counts["scan_error_count"] == 0,
        "directory_stable_during_scan": True,
        "hidden_policy": (
            "included" if include_hidden else "ignored_for_emptiness"
        ),
        "symbolic_links_followed_inside_directory": False,
        "entry_classification": (
            "regular_files_directories_links_other_unavailable"
        ),
    }
    if error_samples:
        details["scan_error_samples"] = error_samples
    return details


def _message(target, counts, is_empty):
    if is_empty:
        message = (
            f"Directory '{target.absolute_path}' is empty under the selected "
            "hidden-item policy."
        )
    else:
        message = (
            f"Directory '{target.absolute_path}' is not empty: "
            f"{counts['considered_entries']} considered entries "
            f"({counts['file_count']} files, "
            f"{counts['directory_count']} directories, "
            f"{counts['symlink_count']} links, "
            f"{counts['other_count']} other)."
        )
    if counts["ignored_hidden_entries"]:
        message += (
            f" {counts['ignored_hidden_entries']} hidden entries were ignored "
            "for the emptiness decision."
        )
    return message


def _success(target, counts, error_samples, include_hidden):
    is_empty = counts["considered_entries"] == 0
    details = _details(target, counts, error_samples, include_hidden)
    result = {
        "success": True,
        "message": _message(target, counts, is_empty),
        "directory_path": str(target.absolute_path),
        "analyzed_path": str(target.analyzed_path),
        "is_empty": is_empty,
        "include_hidden": include_hidden,
        "item_count": counts["considered_entries"],
        "file_count": counts["file_count"],
        "directory_count": counts["directory_count"],
        "symlink_count": counts["symlink_count"],
        "details": details,
    }
    if not details["scan_complete"]:
        result["warnings"] = [
            "One or more entries could not be fully classified; they still "
            "counted as present, and bounded error evidence is available."
        ]
    return result


def execute_directory_empty(
    command,
    directory_path,
    include_hidden=False,
    follow_symlinks=False,
):
    """Return exact counts only when the directory remains stable."""
    include_hidden, follow_links, error = _normalize(
        command, include_hidden, follow_symlinks
    )
    if error is not None:
        return error
    target, error = validate_directory(
        directory_path, follow_symlinks=follow_links
    )
    if error is not None:
        return error
    counts = command._empty_counts()
    error_samples = []
    try:
        counts, error_samples = _scan(command, target, include_hidden)
    except DirectoryChangedDuringScanError as exc:
        return command._changed_failure(
            target, counts, error_samples, exc
        )
    except OSError as exc:
        return _scan_failure(target, counts, exc)
    return _success(target, counts, error_samples, include_hidden)
