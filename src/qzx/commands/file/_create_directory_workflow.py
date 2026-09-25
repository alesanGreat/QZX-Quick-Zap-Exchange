"""Batch orchestration and result assembly for createDirectory."""

from __future__ import annotations

import os


def create_directories(command, directory_paths):
    """Create a batch while preserving per-request evidence."""
    failure = _batch_limit_failure(command, directory_paths)
    if failure is not None:
        return failure

    operations, first_request_by_identity = _build_operations(
        command,
        directory_paths,
    )
    counts = _operation_counts(
        directory_paths,
        operations,
        first_request_by_identity,
    )
    details = {
        **counts,
        "filesystem_changed": any(
            operation["changed"] for operation in operations
        ),
        "link_traversal_allowed": False,
        "rollback_policy": "empty_directories_created_by_a_failed_target",
        "operations": operations,
    }
    return _batch_result(operations, counts, details)


def _batch_limit_failure(command, directory_paths):
    if not directory_paths:
        return {
            "success": False,
            "error_code": "missing_argument",
            "error": "No directory paths were provided.",
            "message": "Provide at least one directory path to create.",
        }
    if len(directory_paths) <= command.MAX_PATHS:
        return None
    return {
        "success": False,
        "error_code": "too_many_paths",
        "error": (
            f"createDirectory accepts at most {command.MAX_PATHS} paths per "
            f"invocation; received {len(directory_paths)}."
        ),
        "message": "Split this directory batch into smaller invocations.",
        "details": {
            "requested_count": len(directory_paths),
            "maximum_path_count": command.MAX_PATHS,
            "filesystem_changed": False,
        },
    }


def _build_operations(command, directory_paths):
    operations = []
    first_request_by_identity = {}
    for request_index, requested_path in enumerate(directory_paths, start=1):
        normalized, requested_text, error = command._normalize_path(
            requested_path
        )
        if error is not None:
            operations.append(
                _invalid_operation(request_index, requested_text, error)
            )
            continue
        identity = os.path.normcase(os.path.normpath(str(normalized)))
        duplicate_of = first_request_by_identity.get(identity)
        if duplicate_of is not None:
            operations.append(
                _duplicate_operation(
                    request_index,
                    requested_text,
                    normalized,
                    duplicate_of,
                )
            )
            continue
        first_request_by_identity[identity] = request_index
        operations.append(
            command._create_one(
                normalized,
                requested_text=requested_text,
                request_index=request_index,
            )
        )
    return operations, first_request_by_identity


def _invalid_operation(request_index, requested_text, error):
    return {
        "request_index": request_index,
        "requested_path": requested_text,
        "status": "failed",
        "changed": False,
        **error,
    }


def _duplicate_operation(
    request_index,
    requested_text,
    normalized,
    duplicate_of,
):
    return {
        "request_index": request_index,
        "requested_path": requested_text,
        "path": str(normalized),
        "status": "duplicate",
        "changed": False,
        "duplicate_of_request_index": duplicate_of,
    }


def _operation_counts(directory_paths, operations, first_request_by_identity):
    return {
        "requested": len(directory_paths),
        "normalized_unique": len(first_request_by_identity),
        "created": _status_count(operations, "created"),
        "already_existed": _status_count(operations, "already_exists"),
        "duplicates": _status_count(operations, "duplicate"),
        "failed": _status_count(operations, "failed"),
        "directories_created": sum(
            len(operation.get("created_paths", []))
            for operation in operations
        ),
        "directories_rolled_back": sum(
            len(operation.get("rolled_back_paths", []))
            for operation in operations
        ),
        "directories_retained_after_command": sum(
            _retained_count(operation) for operation in operations
        ),
    }


def _status_count(operations, status):
    return sum(operation["status"] == status for operation in operations)


def _retained_count(operation):
    if operation.get("status") == "created":
        return len(operation.get("created_paths", []))
    return len(operation.get("remaining_created_paths", []))


def _batch_result(operations, counts, details):
    if counts["failed"]:
        return _failed_batch_result(operations, counts, details)
    return {
        "success": True,
        "message": (
            f"Created {counts['created']} target director"
            f"{'ies' if counts['created'] != 1 else 'y'}; "
            f"{counts['already_existed']} already existed and "
            f"{counts['duplicates']} duplicate"
            f"{'s' if counts['duplicates'] != 1 else ''} were skipped."
        ),
        "details": details,
    }


def _failed_batch_result(operations, counts, details):
    completed = counts["created"] + counts["already_existed"]
    error_code = (
        "partial_directory_creation"
        if completed
        else "directory_creation_failed"
    )
    return {
        "success": False,
        "error_code": error_code,
        "error": (
            f"{counts['failed']} of {len(operations)} path request"
            f"{'s' if len(operations) != 1 else ''} failed."
        ),
        "message": (
            f"Created {counts['created']} target director"
            f"{'ies' if counts['created'] != 1 else 'y'}; "
            f"{counts['already_existed']} already existed, "
            f"{counts['duplicates']} duplicate"
            f"{'s' if counts['duplicates'] != 1 else ''} were skipped, "
            f"and {counts['failed']} failed."
        ),
        "details": details,
    }
