"""Result orchestration for ``getProjectTree``."""

from ._project_tree_model import _TreeScanState


def _options(command, dir_path, max_depth, exclude_dirs, include_files, max_entries):
    path, failure = command._normalize_directory(dir_path)
    if failure:
        return None, failure
    depth, failure = command._bounded_integer(
        max_depth, field="max_depth", minimum=0, maximum=command.MAX_DEPTH
    )
    if failure:
        return None, failure
    limit, failure = command._bounded_integer(
        max_entries, field="max_entries", minimum=1, maximum=command.MAX_ENTRIES
    )
    if failure:
        return None, failure
    show_files = command._normalize_boolean(include_files)
    if show_files is None:
        return None, {
            "success": False,
            "error_code": "invalid_include_files",
            "error": "include_files must be a boolean or an unambiguous true/false token.",
            "message": "Choose whether regular files appear in the project tree.",
        }
    excludes, failure = command._normalize_excludes(exclude_dirs)
    return (path, depth, limit, show_files, excludes), failure


def _details(state):
    details = {
        "entry_count": state.entry_count,
        "tree_node_count_including_root": state.entry_count + 1,
        "directory_count": state.directory_count,
        "file_count": state.file_count,
        "symlink_count": state.symlink_count,
        "other_count": state.other_count,
        "unavailable_count": state.unavailable_count,
        "excluded_directory_count": state.excluded_directory_count,
        "skipped_file_count": state.skipped_file_count,
        "scan_complete": state.scan_error_count == 0 and not state.entry_limit_reached,
        "scan_error_count": state.scan_error_count,
        "entry_limit_reached": state.entry_limit_reached,
        "symbolic_links_followed": False,
        "symlink_policy": "listed_not_followed",
        "sorting": "directories_files_links_other_then_casefolded_name",
    }
    if state.scan_error_samples:
        details["scan_error_samples"] = state.scan_error_samples
    return details


def _warnings(state):
    warnings = []
    if state.entry_limit_reached:
        warnings.append("The retained-entry limit was reached; the tree is intentionally partial.")
    if state.scan_error_count:
        warnings.append(
            "{} filesystem entr{} could not be read; the tree contains bounded error evidence.".format(
                state.scan_error_count, "y" if state.scan_error_count == 1 else "ies"
            )
        )
    return warnings


def _root_failure(path, node, tree_text, details):
    error = node["scan_error"]
    return {
        "success": False,
        "error_code": "directory_scan_failed",
        "error": f"{error['error_type']}: {error['error']}",
        "message": f"QZX could not read the root directory '{path}'.",
        "dir_path": str(path),
        "tree_text": tree_text,
        "tree_structure": node,
        "details": details,
    }


def execute_project_tree(command, dir_path=".", max_depth=2, exclude_dirs=None, include_files=True, max_entries=10_000):
    options, failure = _options(
        command, dir_path, max_depth, exclude_dirs, include_files, max_entries
    )
    if failure:
        return failure
    path, depth, limit, show_files, excludes = options
    state = _TreeScanState(root=path, max_entries=limit)
    root = {"name": path.name or str(path), "type": "directory", "children": []}
    command._populate_directory(
        root, path, current_depth=0, max_depth=depth, excludes=excludes,
        include_files=show_files, state=state,
    )
    details = _details(state)
    tree_text = command._render_tree(root)
    if root.get("scan_error"):
        return _root_failure(path, root, tree_text, details)
    result = {
        "success": True,
        "message": f"Generated a project tree for '{path}' with {state.entry_count} retained descendant{'s' if state.entry_count != 1 else ''}; descendant links were listed but not followed.",
        "dir_path": str(path),
        "max_depth": depth,
        "max_entries": limit,
        "exclude_dirs": sorted(excludes),
        "include_files": show_files,
        "tree_text": tree_text,
        "tree_structure": root,
        "details": details,
    }
    warnings = _warnings(state)
    if warnings:
        result["warnings"] = warnings
    return result
