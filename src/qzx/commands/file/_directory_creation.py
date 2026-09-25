"""Single-target creation and rollback for createDirectory."""

from __future__ import annotations

import os


def create_one_directory(
    command,
    path,
    *,
    requested_text,
    request_index,
):
    """Create one target without traversing links."""
    base = {
        "request_index": request_index,
        "requested_path": requested_text,
        "path": str(path),
    }
    missing_components, terminal = _inspect_components(command, path, base)
    if terminal is not None:
        return terminal

    created_paths, concurrent_directories, terminal = _create_missing(
        command,
        path,
        base,
        missing_components,
    )
    if terminal is not None:
        return terminal
    return _verify_created_target(
        command,
        path,
        base,
        created_paths,
        concurrent_directories,
    )


def _inspect_components(command, path, base):
    missing = []
    try:
        for component in command._path_components(path):
            entry_type = command._path_type(component)
            terminal = _component_terminal(base, path, component, entry_type)
            if terminal is not None:
                return None, terminal
            if entry_type == "missing":
                missing.append(component)
    except OSError as exc:
        return None, {
            **base,
            "status": "failed",
            "changed": False,
            "error_code": "path_inspection_failed",
            "error": f"{type(exc).__name__}: {exc}",
        }
    return missing, None


def _component_terminal(base, target, component, entry_type):
    if entry_type == "missing":
        return None
    if entry_type == "link":
        return {
            **base,
            "status": "failed",
            "changed": False,
            "error_code": "symlink_path_blocked",
            "error": (
                "Directory creation does not traverse symbolic links or "
                f"junctions; blocked component '{component}'."
            ),
            "blocked_component": str(component),
        }
    if component != target and entry_type != "directory":
        return _parent_conflict(base, component, entry_type)
    if component == target:
        return _existing_target(base, target, entry_type)
    return None


def _parent_conflict(base, component, entry_type):
    return {
        **base,
        "status": "failed",
        "changed": False,
        "error_code": "parent_not_directory",
        "error": (
            f"Parent component '{component}' is {entry_type}, not a directory."
        ),
        "blocked_component": str(component),
        "blocked_component_type": entry_type,
    }


def _existing_target(base, target, entry_type):
    if entry_type == "directory":
        return {
            **base,
            "status": "already_exists",
            "changed": False,
            "created_paths": [],
        }
    return {
        **base,
        "status": "failed",
        "changed": False,
        "error_code": "path_conflict",
        "error": (
            f"Target '{target}' already exists as {entry_type}, not a directory."
        ),
        "existing_type": entry_type,
    }


def _create_missing(command, target, base, missing_components):
    created_paths = []
    concurrent_directories = []
    for component in missing_components:
        terminal = _create_component(
            command,
            target,
            base,
            component,
            created_paths,
            concurrent_directories,
        )
        if terminal is not None:
            return created_paths, concurrent_directories, terminal
    return created_paths, concurrent_directories, None


def _create_component(
    command,
    target,
    base,
    component,
    created_paths,
    concurrent_directories,
):
    try:
        command._mkdir(component)
        created_paths.append(component)
        return None
    except FileExistsError:
        return _handle_concurrent_entry(
            command,
            target,
            base,
            component,
            created_paths,
            concurrent_directories,
        )
    except OSError as exc:
        return command._creation_failure(
            base,
            target,
            created_paths,
            "directory_create_failed",
            exc,
        )


def _handle_concurrent_entry(
    command,
    target,
    base,
    component,
    created_paths,
    concurrent_directories,
):
    try:
        concurrent_type = command._path_type(component)
    except OSError as exc:
        return command._creation_failure(
            base,
            target,
            created_paths,
            "path_inspection_failed",
            exc,
        )
    if concurrent_type == "directory":
        concurrent_directories.append(component)
        return None
    return command._creation_failure(
        base,
        target,
        created_paths,
        "concurrent_path_conflict",
        FileExistsError(
            f"'{component}' concurrently became {concurrent_type}."
        ),
    )


def _verify_created_target(
    command,
    path,
    base,
    created_paths,
    concurrent_directories,
):
    try:
        final_type = command._path_type(path)
    except OSError as exc:
        return command._creation_failure(
            base,
            path,
            created_paths,
            "path_inspection_failed",
            exc,
        )
    if final_type != "directory":
        return command._creation_failure(
            base,
            path,
            created_paths,
            "directory_verification_failed",
            OSError(f"Target verified as {final_type}, not directory."),
        )
    return {
        **base,
        "status": "created" if created_paths else "already_exists",
        "changed": bool(created_paths),
        "created_paths": [str(component) for component in created_paths],
        "concurrent_directories": [
            str(component) for component in concurrent_directories
        ],
    }


def creation_failure(
    command,
    base,
    target,
    created_paths,
    error_code,
    error,
):
    """Rollback empty directories created for a failed target."""
    rolled_back = []
    rollback_errors = []
    for component in reversed(created_paths):
        try:
            command._rmdir(component)
            rolled_back.append(component)
        except OSError as rollback_error:
            rollback_errors.append(
                {
                    "path": str(component),
                    "error_type": type(rollback_error).__name__,
                    "error": str(rollback_error),
                }
            )

    remaining = [
        component
        for component in created_paths
        if os.path.lexists(component)
    ]
    return {
        **base,
        "status": "failed",
        "changed": bool(remaining),
        "error_code": error_code,
        "error": (
            f"Could not create directory '{target}': "
            f"{type(error).__name__}: {error}"
        ),
        "created_paths": [str(component) for component in created_paths],
        "rolled_back_paths": [str(component) for component in rolled_back],
        "remaining_created_paths": [str(component) for component in remaining],
        "rollback_errors": rollback_errors,
    }
