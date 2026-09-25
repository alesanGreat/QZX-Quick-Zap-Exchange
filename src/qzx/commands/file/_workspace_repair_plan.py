"""Secure saved-plan reader for repairWorkspace."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

from qzx.core.workspace_audit import MAX_PLAN_BYTES, WorkspaceAuditError


def load_repair_plan(plan_file):
    """Load one regular UTF-8 JSON plan without following links."""
    plan_path = _resolve_plan_path(plan_file)
    before_open = _validated_plan_stat(plan_path)
    document = _read_plan_document(plan_path, before_open)
    return plan_path, _unwrap_plan(document)


def _resolve_plan_path(plan_file):
    if plan_file in {None, ""}:
        raise WorkspaceAuditError(
            "plan_file_required",
            "repairWorkspace requires a saved auditWorkspace plan.",
            {
                "remediation": (
                    "Run 'qzx auditWorkspace . --plan-file "
                    "qzx-repair-plan.json --json' first."
                )
            },
        )
    path = Path(plan_file).expanduser()
    path = Path(os.path.abspath(os.fspath(path)))
    if not os.path.lexists(path):
        raise WorkspaceAuditError(
            "plan_file_not_found",
            "Plan file '{}' does not exist.".format(path),
            {"plan_file": str(path)},
        )
    if os.path.islink(path) or (
        hasattr(os.path, "isjunction") and os.path.isjunction(path)
    ):
        raise WorkspaceAuditError(
            "plan_file_link_refused",
            "Plan file '{}' is a symbolic link or junction.".format(path),
            {"plan_file": str(path)},
        )
    return path


def _validated_plan_stat(plan_path):
    info = os.stat(plan_path, follow_symlinks=False)
    if not stat.S_ISREG(info.st_mode):
        raise WorkspaceAuditError(
            "plan_file_not_regular",
            "Plan path '{}' is not a regular file.".format(plan_path),
            {"plan_file": str(plan_path)},
        )
    if info.st_size > MAX_PLAN_BYTES:
        raise WorkspaceAuditError(
            "plan_file_too_large",
            "Plan file is {} bytes; the limit is {} bytes.".format(
                info.st_size,
                MAX_PLAN_BYTES,
            ),
            {
                "plan_file": str(plan_path),
                "size_bytes": info.st_size,
            },
        )
    return info


def _read_plan_document(plan_path, before_open):
    descriptor = None
    try:
        descriptor = _open_plan_descriptor(plan_path)
        opened = os.fstat(descriptor)
        after_open = os.stat(plan_path, follow_symlinks=False)
        _verify_same_plan_inode(
            plan_path,
            before_open,
            opened,
            after_open,
        )
        with os.fdopen(descriptor, "r", encoding="utf-8") as handle:
            descriptor = None
            return json.load(handle)
    except WorkspaceAuditError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise WorkspaceAuditError(
            "plan_file_invalid_json",
            "Plan file '{}' is not valid UTF-8 JSON: {}.".format(
                plan_path,
                exc,
            ),
            {"plan_file": str(plan_path)},
        ) from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _open_plan_descriptor(plan_path):
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    return os.open(plan_path, flags)


def _verify_same_plan_inode(
    plan_path,
    before_open,
    opened,
    after_open,
):
    same_inode = (
        (before_open.st_dev, before_open.st_ino)
        == (opened.st_dev, opened.st_ino)
        and (after_open.st_dev, after_open.st_ino)
        == (opened.st_dev, opened.st_ino)
    )
    if stat.S_ISREG(opened.st_mode) and same_inode:
        return
    raise WorkspaceAuditError(
        "plan_file_changed_during_read",
        "Plan file '{}' changed while it was being opened.".format(
            plan_path
        ),
        {"plan_file": str(plan_path)},
    )


def _unwrap_plan(document):
    if (
        isinstance(document, dict)
        and isinstance(document.get("details"), dict)
        and isinstance(document["details"].get("plan"), dict)
    ):
        return document["details"]["plan"]
    return document
