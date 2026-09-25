"""Filesystem scanning for getCurrentDirectory."""

from __future__ import annotations

import heapq
import os
import stat
from collections import Counter
from pathlib import Path


def entry_type(entry):
    """Classify a directory entry without following links."""
    is_junction = getattr(os.path, "isjunction", None)
    if entry.is_symlink() or (is_junction is not None and is_junction(entry.path)):
        return "symlink"
    if entry.is_file(follow_symlinks=False):
        return "file"
    if entry.is_dir(follow_symlinks=False):
        return "directory"
    return "other"


def is_hidden(entry, entry_stat=None):
    """Recognize dotfiles and the Windows hidden-file attribute."""
    if entry.name.startswith("."):
        return True
    if os.name != "nt":
        return False
    try:
        metadata = entry_stat or entry.stat(follow_symlinks=False)
        hidden_flag = getattr(stat, "FILE_ATTRIBUTE_HIDDEN", 0x2)
        return bool(getattr(metadata, "st_file_attributes", 0) & hidden_flag)
    except OSError:
        return False


def record_scan_error(errors, path, error, limit):
    """Count every scan error while retaining a bounded sample."""
    errors["count"] += 1
    if len(errors["samples"]) < limit:
        errors["samples"].append(
            {
                "path": str(path),
                "error_type": type(error).__name__,
                "error": str(error),
            }
        )


def _preview_item(entry, kind, metadata, format_bytes, iso_timestamp):
    item = {"name": entry.name, "type": kind}
    if kind == "file":
        item["size_bytes"] = metadata.st_size
        item["size_formatted"] = format_bytes(metadata.st_size)
    item["modified_at"] = iso_timestamp(metadata.st_mtime)
    return item


def _consume_current_entry(entry, state, include_preview, limit, callbacks):
    counts, names, preview, errors = (
        state["counts"], state["names"], state["preview"], state["errors"]
    )
    names.add(entry.name)
    kind = None
    try:
        kind = entry_type(entry)
        counts[kind] += 1
        if is_hidden(entry):
            counts["hidden"] += 1
        metadata = None
        if kind == "file":
            metadata = entry.stat(follow_symlinks=False)
            state["immediate_file_size"] += metadata.st_size
        if include_preview:
            metadata = metadata or entry.stat(follow_symlinks=False)
            preview.append(
                _preview_item(entry, kind, metadata, callbacks["format_bytes"],
                              callbacks["iso_timestamp"])
            )
    except OSError as exc:
        if kind is None:
            counts["other"] += 1
        record_scan_error(errors, Path(state["directory"]) / entry.name, exc, limit)


def _current_result(state, project_markers, format_bytes):
    counts, errors = state["counts"], state["errors"]
    total = sum(counts[kind] for kind in ("file", "directory", "symlink", "other"))
    result = {
        "scope": "current_level",
        "entry_count": total,
        "file_count": counts["file"],
        "directory_count": counts["directory"],
        "symlink_count": counts["symlink"],
        "other_count": counts["other"],
        "hidden_count": counts["hidden"],
        "is_empty": total == 0 and errors["count"] == 0,
        "immediate_files_size_bytes": state["immediate_file_size"],
        "immediate_files_size_formatted": format_bytes(state["immediate_file_size"]),
        "detected_project_markers": sorted(state["names"] & project_markers),
        "scan_complete": errors["count"] == 0,
        "scan_error_count": errors["count"],
    }
    if errors["samples"]:
        result["scan_error_samples"] = errors["samples"]
    return result


def scan_current_level(directory, include_preview, limit, project_markers,
                       format_bytes, iso_timestamp):
    """Count and optionally preview entries directly inside a directory."""
    state = {
        "directory": directory,
        "counts": Counter(),
        "immediate_file_size": 0,
        "names": set(),
        "preview": [],
        "errors": {"count": 0, "samples": []},
    }
    try:
        with os.scandir(directory) as entries:
            for entry in entries:
                _consume_current_entry(
                    entry, state, include_preview, limit,
                    {"format_bytes": format_bytes, "iso_timestamp": iso_timestamp},
                )
    except OSError as exc:
        record_scan_error(state["errors"], directory, exc, limit)
    result = _current_result(state, project_markers, format_bytes)
    if include_preview:
        order = {"directory": 0, "file": 1, "symlink": 2, "other": 3}
        state["preview"].sort(
            key=lambda item: (order[item["type"]], item["name"].casefold(), item["name"])
        )
        result["entry_preview"] = state["preview"][:limit]
        result["entry_preview_count"] = min(len(state["preview"]), limit)
        result["entry_preview_truncated"] = len(state["preview"]) > limit
    return result


def _push_ranked(heap, item, limit):
    if len(heap) < limit:
        heapq.heappush(heap, item)
    elif item > heap[0]:
        heapq.heapreplace(heap, item)


def _consume_recursive_file(entry, entry_path, directory, state, include_details, limit):
    metadata = entry.stat(follow_symlinks=False)
    size = metadata.st_size
    state["total_size"] += size
    if not include_details:
        return
    extension = Path(entry.name).suffix.lower() or "(no extension)"
    state["extension_files"][extension] += 1
    state["extension_sizes"][extension] += size
    relative = os.path.relpath(entry_path, directory)
    _push_ranked(state["largest"], (size, relative.casefold(), relative), limit)
    _push_ranked(
        state["recent"],
        (metadata.st_mtime, relative.casefold(), relative, size),
        limit,
    )


def _walk_recursive(directory, include_details, limit, state):
    stack = [Path(directory)]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    path = current / entry.name
                    kind = None
                    try:
                        kind = entry_type(entry)
                        state["counts"][kind] += 1
                        if is_hidden(entry):
                            state["counts"]["hidden"] += 1
                        if kind == "directory":
                            stack.append(path)
                        elif kind == "file":
                            _consume_recursive_file(
                                entry, path, directory, state, include_details, limit
                            )
                    except OSError as exc:
                        if kind is None:
                            state["counts"]["other"] += 1
                        record_scan_error(state["errors"], path, exc, limit)
        except OSError as exc:
            record_scan_error(state["errors"], current, exc, limit)


def _extension_rows(state, limit, format_bytes):
    files, sizes = state["extension_files"], state["extension_sizes"]
    ordered = sorted(files, key=lambda ext: (-files[ext], -sizes[ext], ext))
    selected, omitted = ordered[:limit], ordered[limit:]
    rows = [
        {
            "extension": ext,
            "file_count": files[ext],
            "size_bytes": sizes[ext],
            "size_formatted": format_bytes(sizes[ext]),
        }
        for ext in selected
    ]
    omitted_row = {
        "group_count": len(omitted),
        "file_count": sum(files[ext] for ext in omitted),
        "size_bytes": sum(sizes[ext] for ext in omitted),
    }
    return ordered, omitted, rows, omitted_row


def _add_recursive_details(result, state, limit, format_bytes, iso_timestamp):
    ordered, omitted, rows, omitted_row = _extension_rows(state, limit, format_bytes)
    result["extensions"] = rows
    result["extension_group_count"] = len(ordered)
    result["extensions_truncated"] = bool(omitted)
    result["omitted_extensions"] = omitted_row
    result["largest_files"] = [
        {
            "relative_path": path,
            "size_bytes": size,
            "size_formatted": format_bytes(size),
        }
        for size, _normalized, path in sorted(state["largest"], reverse=True)
    ]
    result["recently_modified_files"] = [
        {
            "relative_path": path,
            "modified_at": iso_timestamp(modified),
            "size_bytes": size,
            "size_formatted": format_bytes(size),
        }
        for modified, _normalized, path, size in sorted(state["recent"], reverse=True)
    ]


def scan_recursive(directory, include_details, limit, format_bytes, iso_timestamp):
    """Perform one bounded-memory recursive analysis."""
    state = {
        "counts": Counter(),
        "extension_files": Counter(),
        "extension_sizes": Counter(),
        "total_size": 0,
        "largest": [],
        "recent": [],
        "errors": {"count": 0, "samples": []},
    }
    _walk_recursive(directory, include_details, limit, state)
    counts, errors = state["counts"], state["errors"]
    result = {
        "scope": "recursive_descendants",
        "file_count": counts["file"],
        "directory_count": counts["directory"],
        "symlink_count": counts["symlink"],
        "other_count": counts["other"],
        "hidden_count": counts["hidden"],
        "total_size_bytes": state["total_size"],
        "total_size_formatted": format_bytes(state["total_size"]),
        "size_measurement": (
            "Logical bytes in regular files; directory metadata and "
            "symbolic-link targets are excluded"
        ),
        "symbolic_links_followed": False,
        "scan_complete": errors["count"] == 0,
        "scan_error_count": errors["count"],
    }
    if errors["samples"]:
        result["scan_error_samples"] = errors["samples"]
    if include_details:
        _add_recursive_details(result, state, limit, format_bytes, iso_timestamp)
    return result
