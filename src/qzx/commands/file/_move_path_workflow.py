"""MovePath execute orchestration and preflight validation."""

from __future__ import annotations

import os
import stat
import uuid
from pathlib import Path

from qzx.core.path_operation_utils import (
    destination_device,
    is_filesystem_root,
    same_or_nested_path_relationship,
)


def execute_move(command, source, destination, force=False):
    """Move one complete filesystem entry through compatibility hooks."""
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
        force_value,
        require_existing_destination=False,
    )
    if not validation["success"]:
        return validation
    return _commit_move(command, validation["details"])


def _commit_move(command, plan):
    source_path = Path(plan["source"])
    destination_path = Path(plan["destination"])
    failure = _prepare_destination_parent(command, destination_path, plan)
    if failure is not None:
        return failure

    previous_path, failure = _stage_previous_destination(
        command,
        destination_path,
        plan,
    )
    if failure is not None:
        return failure

    operation = command._perform_move(
        source_path,
        destination_path,
        plan["same_filesystem"],
    )
    if not operation["success"]:
        recovery = command._recover_failed_replacement(
            source_path,
            destination_path,
            previous_path,
            operation.get("temporary_path"),
        )
        return command._failure(
            "move_failed",
            (
                f"Move from '{source_path}' to '{destination_path}' failed: "
                f"{operation['error']}. {recovery['message']}"
            ),
            **plan,
            recovery=recovery,
        )
    return _successful_move(
        command,
        plan,
        source_path,
        destination_path,
        previous_path,
        operation,
    )


def _prepare_destination_parent(command, destination_path, plan):
    try:
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        return None
    except OSError as exc:
        return command._failure(
            "destination_parent_failed",
            (
                f"Destination parent '{destination_path.parent}' could not be "
                f"created: {type(exc).__name__}: {exc}"
            ),
            **plan,
        )


def _stage_previous_destination(command, destination_path, plan):
    if not plan["destination_existed"]:
        return None, None
    previous_path = destination_path.with_name(
        f".{destination_path.name}.qzx-previous-{uuid.uuid4().hex}"
    )
    try:
        os.rename(destination_path, previous_path)
        return previous_path, None
    except OSError as exc:
        return None, command._failure(
            "destination_stage_failed",
            (
                "The backed-up destination could not be staged for replacement: "
                f"{type(exc).__name__}: {exc}"
            ),
            **plan,
        )


def _successful_move(
    command,
    plan,
    source_path,
    destination_path,
    previous_path,
    operation,
):
    cleanup, warnings = _cleanup_previous(
        command,
        previous_path,
    )
    result = {
        "success": True,
        "message": (
            f"{plan['source_type'].capitalize()} '{source_path}' moved to "
            f"'{destination_path}'."
        ),
        "details": {
            **plan,
            "status": "moved",
            "source_exists_after": os.path.lexists(source_path),
            "destination_exists_after": os.path.lexists(destination_path),
            "verification": operation["verification"],
            "replacement_cleanup": cleanup,
            "retained_previous_path": (
                str(previous_path)
                if previous_path is not None and os.path.lexists(previous_path)
                else None
            ),
        },
    }
    if warnings:
        result["warnings"] = warnings
    return result


def _cleanup_previous(command, previous_path):
    if previous_path is None:
        return "not_needed", []
    try:
        command._remove_existing_destination(previous_path)
        return "previous destination removed", []
    except OSError as exc:
        return "previous destination retained", [
            (
                "Replacement succeeded, but the previous destination remains "
                f"at '{previous_path}': {type(exc).__name__}: {exc}"
            )
        ]


def preflight_move(
    command,
    source,
    destination,
    force,
    require_existing_destination,
):
    """Build the move plan or return a structured refusal."""
    source_path = Path(os.path.abspath(os.fspath(source)))
    destination_path = Path(os.path.abspath(os.fspath(destination)))
    details = {
        "source": str(source_path),
        "destination": str(destination_path),
        "force": bool(force),
    }
    failure = _path_and_relationship_failure(
        command,
        source_path,
        destination_path,
        details,
    )
    if failure is not None:
        return failure
    source_type, failure = _source_type(command, source_path, details)
    if failure is not None:
        return failure
    details["source_type"] = source_type
    failure = _destination_failure(
        command,
        destination_path,
        force,
        require_existing_destination,
        details,
    )
    if failure is not None:
        return failure
    return _device_preflight(
        command,
        source_path,
        destination_path,
        source_type,
        details,
    )


def _path_and_relationship_failure(
    command,
    source_path,
    destination_path,
    details,
):
    if not os.path.lexists(source_path):
        return command._failure(
            "source_missing",
            f"Source '{source_path}' does not exist, so nothing was moved.",
            **details,
        )
    if is_filesystem_root(source_path) or is_filesystem_root(destination_path):
        return command._failure(
            "filesystem_root_protected",
            "Filesystem roots cannot be used as a move source or destination.",
            **details,
        )
    relationship = same_or_nested_path_relationship(source_path, destination_path)
    details["path_relationship"] = relationship
    return _relationship_failure(command, relationship, details)


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
                "Destination is inside the source. Moving a directory into "
                "itself is not a valid complete move."
            ),
        ),
        "source_within_destination": (
            "source_within_destination",
            (
                "Source is inside the destination. Replacing that destination "
                "could delete the source before the move."
            ),
        ),
    }
    failure = failures.get(relationship)
    if failure is None:
        return None
    return command._failure(failure[0], failure[1], **details)


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
            "Move accepts only regular files, symbolic links, and directories; "
            "special filesystem entries are rejected."
        ),
        **details,
    )


def _destination_failure(
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
    return None


def _device_preflight(
    command,
    source_path,
    destination_path,
    source_type,
    details,
):
    source_device = os.lstat(source_path).st_dev
    try:
        target_device = destination_device(destination_path)
    except OSError as exc:
        return command._failure(
            "destination_device_unknown",
            str(exc),
            **details,
        )
    same_filesystem = source_device == target_device
    details["same_filesystem"] = same_filesystem
    if source_type == "directory" and not same_filesystem:
        return command._failure(
            "cross_filesystem_directory_move_unsupported",
            (
                "QZX refuses cross-filesystem directory moves because they can "
                "leave a partially copied and partially deleted tree. Copy and "
                "verify the directory first, then delete the source as a "
                "separate approved operation."
            ),
            **details,
        )
    return {"success": True, "details": details}
