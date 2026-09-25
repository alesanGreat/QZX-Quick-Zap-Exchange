"""CopyPath execute orchestration and preflight validation."""

from __future__ import annotations

import os
import stat
from pathlib import Path

from qzx.core.path_operation_utils import (
    is_filesystem_root,
    same_or_nested_path_relationship,
)


def execute_copy(command, source, destination, recursive=None, force=False):
    """Run copyPath after validating arguments and path relationships."""
    force_value = command._parse_bool(force)
    if force_value is None:
        return command._failure(
            "invalid_boolean",
            f"force must be true or false; got {force!r}.",
            source=source,
            destination=destination,
        )
    validation = command._preflight(
        source,
        destination,
        recursive,
        force_value,
        require_existing_destination=False,
    )
    if not validation["success"]:
        return validation
    return _commit_copy(command, validation["details"])


def _commit_copy(command, plan):
    source_path = Path(plan["source"])
    destination_path = Path(plan["destination"])
    try:
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        if plan["destination_existed"]:
            command._remove_existing_destination(destination_path)
        operation = command._copy_entry(
            source_path,
            destination_path,
            plan["source_type"],
            plan["recursive"],
        )
    except OSError as exc:
        return command._failure(
            "copy_failed",
            (
                f"Copy from '{source_path}' to '{destination_path}' "
                f"failed: {type(exc).__name__}: {exc}"
            ),
            **plan,
            destination_exists_after=os.path.lexists(destination_path),
        )
    return _copy_success(plan, source_path, destination_path, operation)


def _copy_success(plan, source_path, destination_path, operation):
    return {
        "success": True,
        "message": (
            f"{plan['source_type'].capitalize()} '{source_path}' copied "
            f"to '{destination_path}'."
        ),
        "details": {
            **plan,
            "status": "copied",
            "source_exists_after": os.path.lexists(source_path),
            "destination_exists_after": os.path.lexists(destination_path),
            **operation,
        },
    }


def preflight_copy(
    command,
    source,
    destination,
    recursive,
    force,
    require_existing_destination,
):
    """Build the copy plan or return a structured refusal."""
    source_path = Path(os.path.abspath(os.fspath(source)))
    destination_path = Path(os.path.abspath(os.fspath(destination)))
    details = {
        "source": str(source_path),
        "destination": str(destination_path),
        "force": bool(force),
    }
    failure = _source_preflight(
        command,
        source_path,
        destination_path,
        details,
    )
    if failure is not None:
        return failure
    failure = _recursion_preflight(command, recursive, details)
    if failure is not None:
        return failure
    return _destination_preflight(
        command,
        destination_path,
        force,
        require_existing_destination,
        details,
    )


def _source_preflight(command, source_path, destination_path, details):
    failure = _basic_path_failure(command, source_path, destination_path, details)
    if failure is not None:
        return failure
    relationship = same_or_nested_path_relationship(source_path, destination_path)
    details["path_relationship"] = relationship
    failure = _relationship_failure(command, relationship, details)
    if failure is not None:
        return failure
    source_type, failure = _source_type(command, source_path, details)
    if failure is not None:
        return failure
    details["source_type"] = source_type
    return _directory_source_failure(command, source_path, source_type, details)


def _recursion_preflight(command, recursive, details):
    recursion = command._normalize_recursion(recursive)
    if not recursion["success"]:
        return command._failure(
            recursion["error_code"],
            recursion["message"],
            **details,
        )
    details["recursive"] = recursion["value"]
    if details["source_type"] != "directory" and recursive is not None:
        return command._failure(
            "recursive_not_applicable",
            "recursive applies only to directory sources.",
            **details,
        )
    return None


def _basic_path_failure(command, source_path, destination_path, details):
    if not os.path.lexists(source_path):
        return command._failure(
            "source_missing",
            f"Source '{source_path}' does not exist, so nothing was copied.",
            **details,
        )
    if is_filesystem_root(source_path) or is_filesystem_root(destination_path):
        return command._failure(
            "filesystem_root_protected",
            "Filesystem roots cannot be used as a copy source or destination.",
            **details,
        )
    return None


def _relationship_failure(command, relationship, details):
    failures = {
        "same": (
            "source_equals_destination",
            (
                "Source and destination identify the same filesystem object. "
                "Choose a different destination."
            ),
        ),
        "destination_within_source": (
            "destination_within_source",
            (
                "Destination is inside the source. Copying a directory into "
                "itself can recurse indefinitely and is blocked."
            ),
        ),
        "source_within_destination": (
            "source_within_destination",
            (
                "Source is inside the destination. Replacing that destination "
                "could delete the source before copying it."
            ),
        ),
    }
    failure = failures.get(relationship)
    if failure is None:
        return None
    error_code, message = failure
    return command._failure(error_code, message, **details)


def _source_type(command, source_path, details):
    mode = os.lstat(source_path).st_mode
    if stat.S_ISLNK(mode):
        return "symbolic link", None
    if stat.S_ISDIR(mode):
        return "directory", None
    if stat.S_ISREG(mode):
        return "file", None
    return None, command._failure(
        "unsupported_source_type",
        (
            "Copy accepts only regular files, symbolic links, and directories; "
            "special filesystem entries are rejected."
        ),
        **details,
    )


def _directory_source_failure(command, source_path, source_type, details):
    if source_type != "directory":
        return None
    unsafe_entry = command._first_unsafe_directory_entry(source_path)
    if unsafe_entry is None:
        return None
    return command._failure(
        "unsupported_source_entry",
        (
            f"Directory contains unsupported special entry '{unsafe_entry}'. "
            "Copy accepts only directories, regular files, and symbolic links."
        ),
        **details,
        unsupported_entry=str(unsafe_entry),
    )


def _destination_preflight(
    command,
    destination_path,
    force,
    require_existing_destination,
    details,
):
    destination_existed = os.path.lexists(destination_path)
    details["destination_existed"] = destination_existed
    if require_existing_destination and not destination_existed:
        return command._failure(
            "overwrite_target_missing",
            (
                f"Destination '{destination_path}' does not exist. Omit --force "
                "to create it without an unnecessary safety backup."
            ),
            **details,
        )
    if destination_existed and not force:
        return command._failure(
            "destination_exists",
            (
                f"Destination '{destination_path}' already exists. Use --force "
                "to replace it after a safety backup."
            ),
            **details,
        )
    return {"success": True, "details": details}
