"""Error-aware direct enumeration without interpreting literal parent paths as globs."""

from __future__ import annotations

import fnmatch
import os

from qzx.core.filesystem_references import is_path_reference


def direct_matches(directory, pattern, file_type, exclude_patterns, on_file_found,
                   on_dir_found, on_error):
    """Keep the historical direct-glob hidden-file rule and expose read failures."""
    for entry in _directory_entries(directory, on_error):
        if not _matches_name(entry.name, pattern, exclude_patterns):
            continue
        kind = _entry_kind(entry, on_error)
        if kind is False or (file_type is not None and kind != file_type):
            continue
        callback = on_file_found if kind == "f" else on_dir_found if kind == "d" else None
        if callback:
            callback(entry.path)
        yield entry.path


def _directory_entries(directory, on_error):
    try:
        with os.scandir(directory) as entries:
            yield from entries
    except OSError as exc:
        if on_error:
            on_error(exc)


def _matches_name(name, pattern, exclusions):
    if name.startswith(".") and not pattern.startswith("."):
        return False
    return fnmatch.fnmatch(name, pattern) and not any(
        fnmatch.fnmatch(name, excluded) for excluded in exclusions
    )


def _entry_kind(entry, on_error):
    try:
        if entry.is_file():
            return "f"
        if entry.is_dir():
            return "d"
        return None
    except OSError as exc:
        if on_error:
            on_error(exc)
        return False


def prune_directory_references(root, directories, on_error):
    """Prevent traversal through directory aliases without hiding their names."""
    retained = []
    for name in directories:
        try:
            info = os.stat(os.path.join(root, name), follow_symlinks=False)
        except OSError as exc:
            if on_error:
                on_error(exc)
            continue
        if not is_path_reference(info):
            retained.append(name)
    directories[:] = retained
