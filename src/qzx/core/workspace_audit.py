"""Deterministic, fail-closed workspace audit plans.

The scanner never mutates its target.  Executable cleanup actions include
content fingerprints so a later repair can prove that it is acting on the
same entries that were reviewed.
"""

from __future__ import annotations

from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat

from qzx.core.path_operation_utils import (
    file_sha256,
    files_identical,
    is_filesystem_root,
)


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

IGNORED_DIRECTORY_NAMES = {
    ".git",
    ".hg",
    ".svn",
    ".dropbox",
    ".dropbox.cache",
    "node_modules",
}
DIRECT_BUILD_DIRECTORIES = {
    "__pycache__",
    ".pytest_cache",
    ".sass-cache",
    ".next",
    ".nuxt",
    ".turbo",
}
CONDITIONAL_BUILD_DIRECTORIES = {
    "dist": {"package.json", "pyproject.toml", "setup.py"},
    "build": {
        "package.json",
        "pyproject.toml",
        "setup.py",
        "CMakeLists.txt",
    },
    "target": {"Cargo.toml"},
    "out": {"package.json", "tsconfig.json"},
}
BUILD_FILE_EXTENSIONS = {".pyc", ".pyo", ".class"}
TEMP_DELETE_EXTENSIONS = {".tmp", ".swp", ".temp"}
TEMP_REVIEW_EXTENSIONS = {".log", ".bak"}
ARTIFACT_EXTENSIONS = {
    ".a",
    ".dll",
    ".dylib",
    ".exe",
    ".lib",
    ".o",
    ".obj",
    ".pyd",
    ".so",
}
DUPLICATE_NAME_PATTERNS = (" (1)", " - copy", "_backup", "_copy")


class WorkspaceAuditError(ValueError):
    """A workspace cannot be audited safely with the requested inputs."""

    def __init__(self, code, message, details=None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


def parse_categories(value):
    """Return a deterministic category tuple and reject unknown values."""
    if value is None:
        requested = list(VALID_CATEGORIES)
    elif isinstance(value, str):
        requested = [item.strip().lower() for item in value.split(",") if item.strip()]
    elif isinstance(value, (list, tuple, set)):
        requested = [
            str(item).strip().lower()
            for item in value
            if str(item).strip()
        ]
    else:
        raise WorkspaceAuditError(
            "invalid_categories",
            "categories must be a comma-separated string or a list of names.",
            {"received_type": type(value).__name__},
        )

    if not requested:
        raise WorkspaceAuditError(
            "invalid_categories",
            "At least one workspace audit category is required.",
            {"valid_categories": list(VALID_CATEGORIES)},
        )

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
    return tuple(category for category in VALID_CATEGORIES if category in set(requested))


def validate_max_files(value):
    """Validate the bounded file count used by an audit."""
    if isinstance(value, bool):
        raise WorkspaceAuditError(
            "invalid_max_files",
            "max_files must be an integer, not a boolean.",
        )
    try:
        maximum = int(value)
    except (TypeError, ValueError) as exc:
        raise WorkspaceAuditError(
            "invalid_max_files",
            "max_files must be an integer between 1 and {}.".format(MAX_MAX_FILES),
            {"max_files": value},
        ) from exc
    if maximum < 1 or maximum > MAX_MAX_FILES:
        raise WorkspaceAuditError(
            "invalid_max_files",
            "max_files must be between 1 and {}.".format(MAX_MAX_FILES),
            {"max_files": maximum},
        )
    return maximum


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
            "Filesystem root '{}' cannot be audited for automated repair.".format(
                resolved
            ),
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
    file_hasher = file_sha256 if file_hasher is None else file_hasher
    root = resolve_workspace_root(path)
    selected_categories = parse_categories(categories)
    file_limit = validate_max_files(max_files)
    inventory, scan_errors, ignored_paths, limit_reached = _scan_inventory(
        root,
        file_limit,
    )

    actions = _classify_inventory(
        root,
        inventory,
        selected_categories,
        file_hasher,
    )
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

    executable = [action for action in actions if action["executable"]]
    review_only = [action for action in actions if not action["executable"]]
    category_counts = {
        category: sum(
            1 for action in actions if action["category"] == category
        )
        for category in selected_categories
    }
    plan = {
        "schema_version": PLAN_SCHEMA_VERSION,
        "root": str(root),
        "categories": list(selected_categories),
        "max_files": file_limit,
        "scan_complete": not scan_errors and not limit_reached,
        "scanned_files": sum(
            1
            for entry in inventory.values()
            if entry["type"] in {"file", "symlink", "special"}
        ),
        "scanned_directories": sum(
            1 for entry in inventory.values() if entry["type"] == "directory"
        ),
        "ignored_paths": sorted(ignored_paths),
        "scan_errors": scan_errors,
        "actions": actions,
        "summary": {
            "total_actions": len(actions),
            "executable_actions": len(executable),
            "review_only_actions": len(review_only),
            "recoverable_bytes": sum(
                action.get("size_bytes", 0) for action in executable
            ),
            "category_counts": category_counts,
        },
    }
    plan["plan_id"] = plan_id(plan)
    return plan


def plan_id(plan):
    """Return the content-derived identifier for a complete plan document."""
    content = dict(plan)
    content.pop("plan_id", None)
    return "plan-" + _canonical_digest(content)


def action_id(action):
    """Return a short content-derived identifier for one action."""
    content = dict(action)
    content.pop("id", None)
    return "act-" + _canonical_digest(content)[:20]


def validate_plan_integrity(plan):
    """Validate the untrusted structure and content identifiers of a plan."""
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
    expected_plan_id = plan_id(plan)
    if plan.get("plan_id") != expected_plan_id:
        raise WorkspaceAuditError(
            "plan_integrity_failed",
            "The workspace repair plan identifier does not match its content.",
            {
                "expected_plan_id": expected_plan_id,
                "received_plan_id": plan.get("plan_id"),
            },
        )
    resolve_workspace_root(plan.get("root", ""))
    parse_categories(plan.get("categories"))
    validate_max_files(plan.get("max_files"))
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

    identifiers = set()
    for index, action in enumerate(plan["actions"]):
        _validate_action(action, index)
        if action["id"] in identifiers:
            raise WorkspaceAuditError(
                "invalid_plan",
                "Workspace repair action identifiers must be unique.",
                {"duplicate_action_id": action["id"]},
            )
        identifiers.add(action["id"])
    return plan


def verify_action_fingerprint(root, action):
    """Return ``None`` when an action still matches, otherwise a reason."""
    target = _safe_action_target(root, action["path"])
    expected = action.get("fingerprint")
    try:
        actual = fingerprint_path(target)
    except (OSError, WorkspaceAuditError) as exc:
        return "{}: {}".format(type(exc).__name__, exc)
    if actual != expected:
        return "fingerprint changed"

    if action["kind"] == "delete_duplicate":
        original = _safe_action_target(root, action.get("duplicate_of", ""))
        try:
            original_fingerprint = fingerprint_path(original)
        except (OSError, WorkspaceAuditError) as exc:
            return "duplicate source unavailable: {}: {}".format(
                type(exc).__name__,
                exc,
            )
        if original_fingerprint != action.get("original_fingerprint"):
            return "duplicate source fingerprint changed"
        if not files_identical(target, original):
            return "duplicate and source are no longer byte-identical"
    return None


def fingerprint_path(path):
    """Fingerprint a regular file or an entire non-traversing directory tree."""
    path = Path(path)
    entry_type = _path_type(path)
    if entry_type == "file":
        size = path.stat(follow_symlinks=False).st_size
        return {
            "type": "file",
            "size_bytes": size,
            "sha256": file_sha256(path),
        }
    if entry_type == "directory":
        records = []
        base = path
        stack = [path]
        while stack:
            directory = stack.pop()
            with os.scandir(directory) as scanner:
                entries = sorted(
                    scanner,
                    key=lambda item: (item.name.casefold(), item.name),
                )
            directories = []
            for entry in entries:
                entry_path = Path(entry.path)
                relative = entry_path.relative_to(base).as_posix()
                child_type = _entry_type(entry)
                if child_type == "directory":
                    records.append({"path": relative, "type": "directory"})
                    directories.append(entry_path)
                elif child_type == "file":
                    child_size = entry.stat(follow_symlinks=False).st_size
                    records.append(
                        {
                            "path": relative,
                            "type": "file",
                            "size_bytes": child_size,
                            "sha256": file_sha256(entry_path),
                        }
                    )
                elif child_type == "symlink":
                    records.append(
                        {
                            "path": relative,
                            "type": "symlink",
                            "target": os.readlink(entry_path),
                        }
                    )
                else:
                    raise WorkspaceAuditError(
                        "special_entry_refused",
                        "Directory '{}' contains unsupported special entry '{}'.".format(
                            path,
                            relative,
                        ),
                        {"path": str(entry_path), "type": child_type},
                    )
            stack.extend(reversed(directories))
        total_size = sum(record.get("size_bytes", 0) for record in records)
        return {
            "type": "directory",
            "size_bytes": total_size,
            "entries": len(records),
            "tree_sha256": _canonical_digest(records),
        }
    raise WorkspaceAuditError(
        "unsupported_entry_type",
        "Path '{}' is not a regular file or directory.".format(path),
        {"path": str(path), "type": entry_type},
    )


def _scan_inventory(root, max_files):
    inventory = {}
    errors = []
    ignored = []
    file_count = 0
    limit_reached = False
    stack = [root]

    while stack and not limit_reached:
        directory = stack.pop()
        relative_directory = (
            "."
            if directory == root
            else directory.relative_to(root).as_posix()
        )
        try:
            with os.scandir(directory) as scanner:
                entries = sorted(
                    scanner,
                    key=lambda item: (item.name.casefold(), item.name),
                )
        except OSError as exc:
            errors.append(
                {
                    "path": relative_directory,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
            continue

        child_directories = []
        for entry in entries:
            entry_path = Path(entry.path)
            relative = entry_path.relative_to(root).as_posix()
            try:
                entry_type = _entry_type(entry)
            except OSError as exc:
                errors.append(
                    {
                        "path": relative,
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                )
                continue

            if entry_type == "directory":
                if (
                    entry.name in IGNORED_DIRECTORY_NAMES
                    or entry.name.startswith(".qzx-repair-stage-")
                ):
                    ignored.append(relative)
                    continue
                inventory[relative] = {
                    "path": entry_path,
                    "type": "directory",
                    "name": entry.name,
                }
                child_directories.append(entry_path)
                continue

            file_count += 1
            if file_count > max_files:
                limit_reached = True
                errors.append(
                    {
                        "path": relative,
                        "error_type": "ScanLimitExceeded",
                        "error": (
                            "The scan exceeded max_files={}; no resulting plan "
                            "may be applied."
                        ).format(max_files),
                    }
                )
                break

            item = {
                "path": entry_path,
                "type": entry_type,
                "name": entry.name,
            }
            if entry_type == "file":
                try:
                    item["size_bytes"] = entry.stat(
                        follow_symlinks=False
                    ).st_size
                except OSError as exc:
                    errors.append(
                        {
                            "path": relative,
                            "error_type": type(exc).__name__,
                            "error": str(exc),
                        }
                    )
                    continue
            inventory[relative] = item
        stack.extend(reversed(child_directories))
    return inventory, errors, ignored, limit_reached


def _classify_inventory(root, inventory, categories, file_hasher):
    actions = []
    executable_directories = set()

    if "build" in categories:
        for relative, item in inventory.items():
            if item["type"] != "directory":
                continue
            if _nested_under_any(relative, executable_directories):
                continue
            reason = _build_directory_reason(root, relative, item["name"])
            if reason is None:
                continue
            try:
                fingerprint = fingerprint_path(item["path"])
            except (OSError, WorkspaceAuditError) as exc:
                actions.append(
                    _review_action(
                        "build",
                        relative,
                        "review_directory",
                        "Build candidate requires review because it could not be "
                        "fingerprinted safely: {}: {}.".format(
                            type(exc).__name__,
                            exc,
                        ),
                    )
                )
                continue
            executable_directories.add(relative)
            actions.append(
                {
                    "category": "build",
                    "kind": "delete_directory",
                    "path": relative,
                    "reason": reason,
                    "executable": True,
                    "size_bytes": fingerprint["size_bytes"],
                    "fingerprint": fingerprint,
                }
            )

    duplicate_candidates = defaultdict(list)
    for relative, item in inventory.items():
        if _nested_under_any(relative, executable_directories):
            continue
        if item["type"] != "file":
            if (
                "reorganizations" in categories
                and item["type"] in {"symlink", "special"}
            ):
                actions.append(
                    _review_action(
                        "reorganizations",
                        relative,
                        "review_special_entry",
                        "{} entries are never altered automatically.".format(
                            item["type"].capitalize()
                        ),
                    )
                )
            continue

        path = item["path"]
        size = item["size_bytes"]
        suffix = path.suffix.lower()
        action = None
        scheduled_for_deletion = False
        if "build" in categories and suffix in BUILD_FILE_EXTENSIONS:
            action = _file_delete_action(
                "build",
                relative,
                path,
                "Known generated build or interpreter-cache extension.",
            )
        elif "temp" in categories and (
            suffix in TEMP_DELETE_EXTENSIONS or item["name"].endswith("~")
        ):
            action = _file_delete_action(
                "temp",
                relative,
                path,
                "Temporary editor or tool output selected for explicit cleanup.",
            )
        elif "temp" in categories and suffix in TEMP_REVIEW_EXTENSIONS:
            action = _review_action(
                "temp",
                relative,
                "review_file",
                "Logs and backup files can contain valuable recovery evidence.",
                size,
            )
        if action is not None:
            actions.append(action)
            scheduled_for_deletion = bool(action["executable"])

        if "artifacts" in categories and suffix in ARTIFACT_EXTENSIONS:
            actions.append(
                _review_action(
                    "artifacts",
                    relative,
                    "review_file",
                    "Compiled artifacts may be intentional deliverables.",
                    size,
                )
            )

        if "reorganizations" in categories:
            proposed_name, reasons = _proposed_name(item["name"])
            if item["name"] == ".env" and path.parent != root:
                actions.append(
                    _review_action(
                        "reorganizations",
                        relative,
                        "review_move",
                        "Nested .env files can be scope-specific and are never moved automatically.",
                        size,
                        proposed_path=".env",
                    )
                )
            elif proposed_name != item["name"]:
                proposed_relative = (
                    PurePosixPath(relative).parent / proposed_name
                ).as_posix()
                actions.append(
                    _review_action(
                        "reorganizations",
                        relative,
                        "review_rename",
                        "Filename normalization suggestion: {}.".format(
                            ", ".join(reasons)
                        ),
                        size,
                        proposed_path=proposed_relative,
                    )
                )

        if (
            "duplicates" in categories
            and not scheduled_for_deletion
            and size <= MAX_DUPLICATE_BYTES
        ):
            try:
                digest = file_hasher(path)
            except OSError:
                continue
            duplicate_candidates[(size, digest)].append((relative, path))
            if any(pattern in item["name"].lower() for pattern in DUPLICATE_NAME_PATTERNS):
                actions.append(
                    _review_action(
                        "duplicates",
                        relative,
                        "review_filename_pattern",
                        "The filename resembles a copy, but name alone never authorizes deletion.",
                        size,
                    )
                )

    if "duplicates" in categories:
        for (_size, _digest), candidates in sorted(duplicate_candidates.items()):
            candidates.sort(key=lambda item: (item[0].casefold(), item[0]))
            originals = []
            for relative, path in candidates:
                matching = next(
                    (
                        original
                        for original in originals
                        if files_identical(path, original[1])
                    ),
                    None,
                )
                if matching is None:
                    originals.append((relative, path))
                    continue
                target_fingerprint = fingerprint_path(path)
                original_fingerprint = fingerprint_path(matching[1])
                actions.append(
                    {
                        "category": "duplicates",
                        "kind": "delete_duplicate",
                        "path": relative,
                        "duplicate_of": matching[0],
                        "reason": "SHA-256 and exact byte match.",
                        "executable": True,
                        "size_bytes": target_fingerprint["size_bytes"],
                        "fingerprint": target_fingerprint,
                        "original_fingerprint": original_fingerprint,
                    }
                )
    return _deduplicate_actions(actions)


def _build_directory_reason(root, relative, name):
    if name in DIRECT_BUILD_DIRECTORIES:
        return "Known generated cache or build directory name."
    triggers = CONDITIONAL_BUILD_DIRECTORIES.get(name)
    if triggers is None:
        return None
    parent = (root / PurePosixPath(relative)).parent
    matched = sorted(
        trigger
        for trigger in triggers
        if (parent / trigger).is_file() and not _is_link_like(parent / trigger)
    )
    if not matched:
        return None
    return "Generated directory matched parent marker(s): {}.".format(
        ", ".join(matched)
    )


def _file_delete_action(category, relative, path, reason):
    fingerprint = fingerprint_path(path)
    return {
        "category": category,
        "kind": "delete_file",
        "path": relative,
        "reason": reason,
        "executable": True,
        "size_bytes": fingerprint["size_bytes"],
        "fingerprint": fingerprint,
    }


def _review_action(
    category,
    relative,
    kind,
    reason,
    size_bytes=0,
    proposed_path=None,
):
    action = {
        "category": category,
        "kind": kind,
        "path": relative,
        "reason": reason,
        "executable": False,
        "size_bytes": size_bytes,
    }
    if proposed_path is not None:
        action["proposed_path"] = proposed_path
    return action


def _proposed_name(name):
    stem, suffix = os.path.splitext(name)
    reasons = []
    proposed_stem = stem
    proposed_suffix = suffix
    if " " in name:
        proposed_stem = stem.replace(" ", "_")
        reasons.append("spaces in name")
    if suffix and suffix != suffix.lower():
        proposed_suffix = suffix.lower()
        reasons.append("uppercase extension")
    return proposed_stem + proposed_suffix, reasons


def _deduplicate_actions(actions):
    seen = set()
    unique = []
    for action in actions:
        key = (
            action["category"],
            action["kind"],
            action["path"],
            action.get("proposed_path"),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(action)
    return unique


def _nested_under_any(relative, parents):
    candidate = PurePosixPath(relative)
    return any(
        parent == relative or PurePosixPath(parent) in candidate.parents
        for parent in parents
    )


def _validate_action(action, index):
    if not isinstance(action, dict):
        raise WorkspaceAuditError(
            "invalid_plan",
            "Workspace repair action {} must be an object.".format(index),
        )
    for field in ("id", "category", "kind", "path", "reason", "executable"):
        if field not in action:
            raise WorkspaceAuditError(
                "invalid_plan",
                "Workspace repair action {} is missing '{}'.".format(index, field),
            )
    _validate_relative_path(action["path"], "actions[{}].path".format(index))
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
            "Workspace repair action {} identifier does not match its content.".format(
                index
            ),
        )
    if action["executable"]:
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
            _validate_relative_path(
                action.get("duplicate_of"),
                "actions[{}].duplicate_of".format(index),
            )
            if not isinstance(action.get("original_fingerprint"), dict):
                raise WorkspaceAuditError(
                    "invalid_plan",
                    "Duplicate action {} lacks its source fingerprint.".format(index),
                )


def _validate_relative_path(value, field):
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
    return candidate


def _entry_type(entry):
    if entry.is_symlink() or (
        hasattr(os.path, "isjunction") and os.path.isjunction(entry.path)
    ):
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


def _is_link_like(path):
    return os.path.islink(path) or (
        hasattr(os.path, "isjunction") and os.path.isjunction(path)
    )


def _canonical_digest(value):
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
