"""Deterministic, fail-closed workspace audit plans.

The scanner never mutates its target. Executable cleanup actions include
content fingerprints so a later repair can prove that it is acting on the
same entries that were reviewed.
"""

from __future__ import annotations

import os
from pathlib import Path, PurePosixPath
import stat

from qzx.core.path_operation_utils import (
    file_sha256,
    files_identical,
    is_filesystem_root,
)
from qzx.core.workspace_contract import (
    DEFAULT_MAX_FILES,
    MAX_DUPLICATE_BYTES,
    MAX_MAX_FILES,
    MAX_PLAN_BYTES,
    PLAN_SCHEMA_VERSION,
    VALID_CATEGORIES,
    WorkspaceAuditError,
    action_id,
    canonical_digest,
    parse_categories,
    plan_id,
    validate_action,
    validate_max_files,
    validate_relative_path,
)
from qzx.core.workspace_fingerprints import fingerprint_path as _fingerprint_path
from qzx.core.workspace_inventory import (
    ARTIFACT_EXTENSIONS,
    BUILD_FILE_EXTENSIONS,
    CONDITIONAL_BUILD_DIRECTORIES,
    DIRECT_BUILD_DIRECTORIES,
    DUPLICATE_NAME_PATTERNS,
    IGNORED_DIRECTORY_NAMES,
    TEMP_DELETE_EXTENSIONS,
    TEMP_REVIEW_EXTENSIONS,
    build_directory_reason as _build_directory_reason_impl,
    classify_inventory as _classify_inventory_impl,
    deduplicate_actions as _deduplicate_actions_impl,
    file_delete_action as _file_delete_action_impl,
    nested_under_any as _nested_under_any_impl,
    proposed_name as _proposed_name_impl,
    review_action as _review_action_impl,
    scan_inventory as _scan_inventory_impl,
)

__all__ = [
    "ARTIFACT_EXTENSIONS",
    "BUILD_FILE_EXTENSIONS",
    "CONDITIONAL_BUILD_DIRECTORIES",
    "DEFAULT_MAX_FILES",
    "DIRECT_BUILD_DIRECTORIES",
    "DUPLICATE_NAME_PATTERNS",
    "IGNORED_DIRECTORY_NAMES",
    "MAX_DUPLICATE_BYTES",
    "MAX_MAX_FILES",
    "MAX_PLAN_BYTES",
    "PLAN_SCHEMA_VERSION",
    "TEMP_DELETE_EXTENSIONS",
    "TEMP_REVIEW_EXTENSIONS",
    "VALID_CATEGORIES",
    "WorkspaceAuditError",
    "action_id",
    "build_workspace_plan",
    "fingerprint_path",
    "parse_categories",
    "plan_id",
    "resolve_workspace_root",
    "validate_max_files",
    "validate_plan_integrity",
    "verify_action_fingerprint",
]


def resolve_workspace_root(path):
    """Resolve and validate a non-root, non-link workspace directory."""
    supplied = Path(path).expanduser()
    absolute = Path(os.path.abspath(os.fspath(supplied)))
    if not os.path.lexists(absolute):
        raise WorkspaceAuditError(
            "path_not_found",
            "Workspace path '{}' does not exist.".format(path),
            {"path": str(absolute)},
        )
    if _is_link_like(absolute):
        raise WorkspaceAuditError(
            "workspace_link_refused",
            "Workspace path '{}' is a symbolic link or junction.".format(absolute),
            {
                "path": str(absolute),
                "remediation": "Select the real workspace directory explicitly.",
            },
        )
    if not absolute.is_dir():
        raise WorkspaceAuditError(
            "path_not_directory",
            "Workspace path '{}' is not a directory.".format(absolute),
            {"path": str(absolute)},
        )
    resolved = Path(os.path.realpath(absolute))
    if is_filesystem_root(resolved):
        raise WorkspaceAuditError(
            "filesystem_root_refused",
            "Filesystem root '{}' cannot be audited for automated repair.".format(resolved),
            {"path": str(resolved)},
        )
    return resolved


def build_workspace_plan(
    path=".",
    categories=None,
    max_files=DEFAULT_MAX_FILES,
    file_hasher=None,
):
    """Audit a workspace and return a deterministic repair plan."""
    effective_hasher = file_sha256 if file_hasher is None else file_hasher
    root = resolve_workspace_root(path)
    selected_categories = parse_categories(categories)
    file_limit = validate_max_files(max_files)
    inventory, errors, ignored, limit_reached = _scan_inventory(root, file_limit)
    actions = _classify_inventory(
        root,
        inventory,
        selected_categories,
        effective_hasher,
    )
    _finalize_actions(actions)
    return _plan_document(
        root,
        selected_categories,
        file_limit,
        inventory,
        errors,
        ignored,
        limit_reached,
        actions,
    )


def _finalize_actions(actions):
    actions.sort(
        key=lambda action: (
            action["path"].casefold(),
            action["path"],
            action["kind"],
            action["category"],
        )
    )
    for action in actions:
        action["id"] = action_id(action)


def _plan_document(
    root,
    categories,
    max_files,
    inventory,
    errors,
    ignored,
    limit_reached,
    actions,
):
    plan = {
        "schema_version": PLAN_SCHEMA_VERSION,
        "root": str(root),
        "categories": list(categories),
        "max_files": max_files,
        "scan_complete": not errors and not limit_reached,
        **_scan_counts(inventory),
        "ignored_paths": sorted(ignored),
        "scan_errors": errors,
        "actions": actions,
        "summary": _plan_summary(actions, categories),
    }
    plan["plan_id"] = plan_id(plan)
    return plan


def _scan_counts(inventory):
    return {
        "scanned_files": sum(
            1
            for entry in inventory.values()
            if entry["type"] in {"file", "symlink", "special"}
        ),
        "scanned_directories": sum(
            1 for entry in inventory.values() if entry["type"] == "directory"
        ),
    }


def _plan_summary(actions, categories):
    executable = [action for action in actions if action["executable"]]
    return {
        "total_actions": len(actions),
        "executable_actions": len(executable),
        "review_only_actions": len(actions) - len(executable),
        "recoverable_bytes": sum(action.get("size_bytes", 0) for action in executable),
        "category_counts": {
            category: sum(1 for action in actions if action["category"] == category)
            for category in categories
        },
    }


def validate_plan_integrity(plan):
    """Validate the untrusted structure and content identifiers of a plan."""
    _validate_plan_header(plan)
    resolve_workspace_root(plan.get("root", ""))
    parse_categories(plan.get("categories"))
    validate_max_files(plan.get("max_files"))
    _validate_plan_collections(plan)
    _validate_plan_actions(plan["actions"])
    return plan


def _validate_plan_header(plan):
    if not isinstance(plan, dict):
        raise WorkspaceAuditError(
            "invalid_plan",
            "The repair plan must contain one JSON object.",
        )
    if plan.get("schema_version") != PLAN_SCHEMA_VERSION:
        raise WorkspaceAuditError(
            "unsupported_plan_schema",
            "Unsupported workspace repair plan schema: {!r}.".format(
                plan.get("schema_version")
            ),
            {"supported_schema": PLAN_SCHEMA_VERSION},
        )
    expected = plan_id(plan)
    if plan.get("plan_id") != expected:
        raise WorkspaceAuditError(
            "plan_integrity_failed",
            "The workspace repair plan identifier does not match its content.",
            {"expected_plan_id": expected, "received_plan_id": plan.get("plan_id")},
        )


def _validate_plan_collections(plan):
    if not isinstance(plan.get("scan_complete"), bool):
        raise WorkspaceAuditError(
            "invalid_plan",
            "scan_complete must be boolean in a workspace repair plan.",
        )
    if not isinstance(plan.get("actions"), list):
        raise WorkspaceAuditError(
            "invalid_plan",
            "actions must be a list in a workspace repair plan.",
        )


def _validate_plan_actions(actions):
    identifiers = set()
    for index, action in enumerate(actions):
        _validate_action(action, index)
        if action["id"] in identifiers:
            raise WorkspaceAuditError(
                "invalid_plan",
                "Workspace repair action identifiers must be unique.",
                {"duplicate_action_id": action["id"]},
            )
        identifiers.add(action["id"])


def verify_action_fingerprint(root, action):
    """Return ``None`` when an action still matches, otherwise a reason."""
    target = _safe_action_target(root, action["path"])
    mismatch = _fingerprint_mismatch(target, action.get("fingerprint"))
    if mismatch is not None or action["kind"] != "delete_duplicate":
        return mismatch
    original = _safe_action_target(root, action.get("duplicate_of", ""))
    mismatch = _duplicate_source_mismatch(original, action)
    if mismatch is not None:
        return mismatch
    if not files_identical(target, original):
        return "duplicate and source are no longer byte-identical"
    return None


def _fingerprint_mismatch(target, expected):
    try:
        actual = fingerprint_path(target)
    except (OSError, WorkspaceAuditError) as exc:
        return "{}: {}".format(type(exc).__name__, exc)
    if actual != expected:
        return "fingerprint changed"
    return None


def _duplicate_source_mismatch(original, action):
    try:
        actual = fingerprint_path(original)
    except (OSError, WorkspaceAuditError) as exc:
        return "duplicate source unavailable: {}: {}".format(type(exc).__name__, exc)
    if actual != action.get("original_fingerprint"):
        return "duplicate source fingerprint changed"
    return None


def fingerprint_path(path):
    """Fingerprint a file or non-traversing directory using local dependencies."""
    return _fingerprint_path(
        path,
        path_type=_path_type,
        entry_type=_entry_type,
        file_hasher=file_sha256,
        canonical_digest=_canonical_digest,
        error_type=WorkspaceAuditError,
    )


def _scan_inventory(root, max_files):
    return _scan_inventory_impl(root, max_files, entry_type=_entry_type)


def _classify_inventory(root, inventory, categories, file_hasher):
    return _classify_inventory_impl(
        root,
        inventory,
        categories,
        file_hasher,
        fingerprint=fingerprint_path,
        files_equal=files_identical,
        is_link_like=_is_link_like,
    )


def _validate_action(action, index):
    return validate_action(action, index)


def _validate_relative_path(value, field):
    return validate_relative_path(value, field)


def _safe_action_target(root, relative):
    _validate_relative_path(relative, "action path")
    root = Path(root)
    candidate = root.joinpath(*PurePosixPath(relative).parts)
    try:
        common = os.path.commonpath([str(root), str(candidate)])
    except ValueError as exc:
        raise WorkspaceAuditError(
            "invalid_plan_path",
            "Action path '{}' is on another filesystem.".format(relative),
        ) from exc
    if os.path.normcase(common) != os.path.normcase(str(root)):
        raise WorkspaceAuditError(
            "invalid_plan_path",
            "Action path '{}' escapes the workspace.".format(relative),
        )
    _validate_action_ancestors(root, relative)
    return candidate


def _validate_action_ancestors(root, relative):
    current = root
    for part in PurePosixPath(relative).parts[:-1]:
        current = current / part
        if _is_link_like(current):
            raise WorkspaceAuditError(
                "action_ancestor_link_refused",
                "Action path '{}' crosses symbolic link or junction '{}'.".format(
                    relative,
                    current,
                ),
            )
        if not current.is_dir():
            raise WorkspaceAuditError(
                "action_ancestor_invalid",
                "Action path '{}' has a missing or non-directory ancestor '{}'.".format(
                    relative,
                    current,
                ),
            )


def _entry_type(entry):
    if entry.is_symlink() or _is_junction(entry.path):
        return "symlink"
    mode = entry.stat(follow_symlinks=False).st_mode
    if stat.S_ISREG(mode):
        return "file"
    if stat.S_ISDIR(mode):
        return "directory"
    return "special"


def _path_type(path):
    if not os.path.lexists(path):
        return "missing"
    if _is_link_like(path):
        return "symlink"
    mode = os.stat(path, follow_symlinks=False).st_mode
    if stat.S_ISREG(mode):
        return "file"
    if stat.S_ISDIR(mode):
        return "directory"
    return "special"


def _is_junction(path):
    """Recognize Windows junctions across supported Python runtime versions."""
    native_isjunction = getattr(os.path, "isjunction", None)
    if native_isjunction is not None:
        return bool(native_isjunction(path))
    if os.name != "nt":
        return False
    mount_point_tag = getattr(stat, "IO_REPARSE_TAG_MOUNT_POINT", None)
    if mount_point_tag is None:
        return False
    try:
        reparse_tag = os.stat(path, follow_symlinks=False).st_reparse_tag
    except (AttributeError, OSError):
        return False
    return reparse_tag == mount_point_tag


def _is_link_like(path):
    return os.path.islink(path) or _is_junction(path)


def _canonical_digest(value):
    return canonical_digest(value)


def _build_directory_reason(root, relative, name):
    return _build_directory_reason_impl(
        root,
        relative,
        name,
        is_link_like=_is_link_like,
    )


def _file_delete_action(category, relative, path, reason):
    return _file_delete_action_impl(
        category,
        relative,
        path,
        reason,
        fingerprint=fingerprint_path,
    )


def _review_action(*args, **kwargs):
    return _review_action_impl(*args, **kwargs)


def _proposed_name(name):
    return _proposed_name_impl(name)


def _deduplicate_actions(actions):
    return _deduplicate_actions_impl(actions)


def _nested_under_any(relative, parents):
    return _nested_under_any_impl(relative, parents)
