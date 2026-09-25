"""Bounded, symlink-safe traversal for ``getProjectTree``."""

import heapq
import os
from pathlib import Path


def entry_type(_command, entry):
    is_junction = getattr(os.path, "isjunction", None)
    if entry.is_symlink() or (is_junction is not None and is_junction(entry.path)):
        return "symlink"
    if entry.is_dir(follow_symlinks=False):
        return "directory"
    if entry.is_file(follow_symlinks=False):
        return "file"
    return "other"


def candidate_entries(command, entries, *, excludes, include_files, state):
    type_order = {"directory": 0, "file": 1, "symlink": 2, "other": 3, "unavailable": 4}
    for entry in entries:
        classification_error = None
        try:
            kind = command._entry_type(entry)
        except OSError as exc:
            kind, classification_error = "unavailable", exc
            state.record_error(entry.path, exc)
        if kind == "directory" and entry.name.casefold() in excludes:
            state.excluded_directory_count += 1
            continue
        if kind in {"file", "other"} and not include_files:
            state.skipped_file_count += 1
            continue
        yield (type_order[kind], entry.name.casefold(), entry.name), entry, kind, classification_error


def _scan_candidates(command, path, excludes, include_files, state):
    requested = state.remaining_entries + 1
    try:
        with command._scandir(path) as entries:
            candidates = heapq.nsmallest(
                requested,
                command._candidate_entries(
                    entries, excludes=excludes, include_files=include_files, state=state
                ),
                key=lambda candidate: candidate[0],
            )
        return candidates, None
    except OSError as exc:
        state.record_error(path, exc)
        return [], exc


def _record_scan_error(node, error):
    evidence = {"error_type": type(error).__name__, "error": str(error)}
    node["scan_error"] = evidence
    node["children"].append(
        {"name": f"[Scan failed: {type(error).__name__}]", "type": "error", "error": str(error)}
    )


def _add_candidates(command, node, candidates, overflow, depth, maximum, excludes, include_files, state):
    for index, (_sort_key, entry, kind, error) in enumerate(candidates):
        if state.remaining_entries == 0:
            command._append_limit_marker(node, state)
            break
        child = command._entry_node(entry, kind, error, state)
        state.record_entry(kind)
        node["children"].append(child)
        if kind == "directory":
            command._populate_directory(
                child, Path(entry.path), current_depth=depth + 1, max_depth=maximum,
                excludes=excludes, include_files=include_files, state=state,
            )
        if state.remaining_entries == 0 and (index < len(candidates) - 1 or overflow):
            command._append_limit_marker(node, state)
            break


def populate_directory(command, node, path, *, current_depth, max_depth, excludes, include_files, state):
    if current_depth >= max_depth:
        return
    if state.remaining_entries == 0:
        command._append_limit_marker(node, state)
        return
    candidates, error = _scan_candidates(command, path, excludes, include_files, state)
    if error:
        _record_scan_error(node, error)
        return
    overflow = len(candidates) > state.remaining_entries
    if overflow:
        candidates = candidates[: state.remaining_entries]
    _add_candidates(command, node, candidates, overflow, current_depth, max_depth, excludes, include_files, state)
    if overflow and state.remaining_entries > 0:
        command._append_limit_marker(node, state)


def entry_node(command, entry, kind, classification_error, state):
    node = {"name": entry.name, "type": kind}
    if kind == "directory":
        node["children"] = []
    elif kind == "file":
        try:
            node["size_bytes"] = entry.stat(follow_symlinks=False).st_size
        except OSError as exc:
            state.record_error(entry.path, exc)
            node["metadata_error"] = {"error_type": type(exc).__name__, "error": str(exc)}
    elif kind == "symlink":
        _add_link_details(command, entry, node, state)
    elif kind == "unavailable" and classification_error is not None:
        node["error"] = {"error_type": type(classification_error).__name__, "error": str(classification_error)}
    return node


def _add_link_details(command, entry, node, state):
    is_junction = getattr(os.path, "isjunction", None)
    try:
        junction = bool(is_junction is not None and is_junction(entry.path))
    except OSError:
        junction = False
    node.update(link_kind="junction" if junction else "symlink", followed=False)
    try:
        node["target"] = command._readlink(entry.path)
    except OSError as exc:
        state.record_error(entry.path, exc)
        node["target_error"] = {"error_type": type(exc).__name__, "error": str(exc)}


def append_limit_marker(_command, node, state):
    state.entry_limit_reached = True
    if not any(child.get("type") == "truncated" for child in node["children"]):
        node["children"].append({"name": "[Entry limit reached]", "type": "truncated"})


def render_tree(cls, root):
    lines = [cls._display_name(root)]
    cls._render_children(root.get("children", []), "", lines)
    return "\n".join(lines)


def render_children(cls, children, prefix, lines):
    for index, child in enumerate(children):
        last = index == len(children) - 1
        lines.append(prefix + ("└── " if last else "├── ") + cls._display_name(child))
        if child.get("children"):
            cls._render_children(child["children"], prefix + ("    " if last else "│   "), lines)


def display_name(node):
    name = node["name"]
    if node.get("type") == "symlink":
        target = node.get("target", "[target unavailable]")
        return f"{name} -> {target} [{node.get('link_kind', 'symlink')}; not followed]"
    if node.get("type") == "other":
        return f"{name} [other filesystem entry]"
    if node.get("type") == "unavailable":
        return f"{name} [unavailable]"
    return name
