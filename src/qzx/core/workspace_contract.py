"""Validation and content identifiers for workspace repair plans."""

from __future__ import annotations

import hashlib
import json
from pathlib import PurePosixPath


PLAN_SCHEMA_VERSION = 1
DEFAULT_MAX_FILES = 15_000
MAX_MAX_FILES = 100_000
MAX_PLAN_BYTES = 8 * 1024 * 1024
MAX_DUPLICATE_BYTES = 10 * 1024 * 1024
VALID_CATEGORIES = (
    "build",
    "temp",
    "artifacts",
    "duplicates",
    "reorganizations",
)


class WorkspaceAuditError(ValueError):
    """A workspace cannot be audited safely with the requested inputs."""

    def __init__(self, code, message, details=None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


def parse_categories(value):
    """Return a deterministic category tuple and reject unknown values."""
    requested = _requested_categories(value)
    if not requested:
        raise WorkspaceAuditError(
            "invalid_categories",
            "At least one workspace audit category is required.",
            {"valid_categories": list(VALID_CATEGORIES)},
        )
    _reject_unknown_categories(requested)
    requested_set = set(requested)
    return tuple(category for category in VALID_CATEGORIES if category in requested_set)


def _requested_categories(value):
    if value is None:
        return list(VALID_CATEGORIES)
    if isinstance(value, str):
        return [item.strip().lower() for item in value.split(",") if item.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip().lower() for item in value if str(item).strip()]
    raise WorkspaceAuditError(
        "invalid_categories",
        "categories must be a comma-separated string or a list of names.",
        {"received_type": type(value).__name__},
    )


def _reject_unknown_categories(requested):
    unknown = sorted(set(requested) - set(VALID_CATEGORIES))
    if unknown:
        raise WorkspaceAuditError(
            "invalid_categories",
            "Unknown workspace audit categories: {}.".format(", ".join(unknown)),
            {
                "unknown_categories": unknown,
                "valid_categories": list(VALID_CATEGORIES),
            },
        )


def validate_max_files(value):
    """Validate the bounded file count used by an audit."""
    if isinstance(value, bool):
        raise WorkspaceAuditError(
            "invalid_max_files",
            "max_files must be an integer, not a boolean.",
        )
    maximum = _integer_max_files(value)
    if maximum < 1 or maximum > MAX_MAX_FILES:
        raise WorkspaceAuditError(
            "invalid_max_files",
            "max_files must be between 1 and {}.".format(MAX_MAX_FILES),
            {"max_files": maximum},
        )
    return maximum


def _integer_max_files(value):
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise WorkspaceAuditError(
            "invalid_max_files",
            "max_files must be an integer between 1 and {}.".format(MAX_MAX_FILES),
            {"max_files": value},
        ) from exc


def canonical_digest(value):
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def plan_id(plan):
    """Return the content-derived identifier for a complete plan document."""
    content = dict(plan)
    content.pop("plan_id", None)
    return "plan-" + canonical_digest(content)


def action_id(action):
    """Return a short content-derived identifier for one action."""
    content = dict(action)
    content.pop("id", None)
    return "act-" + canonical_digest(content)[:20]


def validate_action(action, index):
    """Validate one untrusted action embedded in a repair plan."""
    if not isinstance(action, dict):
        raise WorkspaceAuditError(
            "invalid_plan",
            "Workspace repair action {} must be an object.".format(index),
        )
    _require_action_fields(action, index)
    validate_relative_path(action["path"], "actions[{}].path".format(index))
    _validate_action_metadata(action, index)
    if action["executable"]:
        _validate_executable_action(action, index)


def _require_action_fields(action, index):
    for field in ("id", "category", "kind", "path", "reason", "executable"):
        if field not in action:
            raise WorkspaceAuditError(
                "invalid_plan",
                "Workspace repair action {} is missing '{}'.".format(index, field),
            )


def _validate_action_metadata(action, index):
    if action["category"] not in VALID_CATEGORIES:
        raise WorkspaceAuditError(
            "invalid_plan",
            "Workspace repair action {} has an unknown category.".format(index),
        )
    if not isinstance(action["executable"], bool):
        raise WorkspaceAuditError(
            "invalid_plan",
            "Workspace repair action {} executable must be boolean.".format(index),
        )
    if action["id"] != action_id(action):
        raise WorkspaceAuditError(
            "plan_integrity_failed",
            "Workspace repair action {} identifier does not match its content.".format(index),
        )


def _validate_executable_action(action, index):
    if action["kind"] not in {
        "delete_file",
        "delete_directory",
        "delete_duplicate",
    }:
        raise WorkspaceAuditError(
            "invalid_plan",
            "Executable workspace action {} has unsupported kind '{}'.".format(
                index,
                action["kind"],
            ),
        )
    if not isinstance(action.get("fingerprint"), dict):
        raise WorkspaceAuditError(
            "invalid_plan",
            "Executable workspace action {} lacks a fingerprint.".format(index),
        )
    if action["kind"] == "delete_duplicate":
        _validate_duplicate_action(action, index)


def _validate_duplicate_action(action, index):
    validate_relative_path(
        action.get("duplicate_of"),
        "actions[{}].duplicate_of".format(index),
    )
    if not isinstance(action.get("original_fingerprint"), dict):
        raise WorkspaceAuditError(
            "invalid_plan",
            "Duplicate action {} lacks its source fingerprint.".format(index),
        )


def validate_relative_path(value, field):
    """Require a POSIX-style path that cannot escape a workspace root."""
    if not isinstance(value, str) or not value or "\\" in value:
        raise WorkspaceAuditError(
            "invalid_plan_path",
            "{} must be a non-empty POSIX-style relative path.".format(field),
        )
    path = PurePosixPath(value)
    if path.is_absolute() or value in {".", ".."} or ".." in path.parts:
        raise WorkspaceAuditError(
            "invalid_plan_path",
            "{} must remain below the workspace root.".format(field),
            {"path": value},
        )
