"""Staging, cleanup, and rollback workflow for repairWorkspace."""

from __future__ import annotations

import os
from pathlib import PurePosixPath
import shutil
import uuid

from qzx.core.workspace_audit import (
    WorkspaceAuditError,
    verify_action_fingerprint,
)


def apply_prepared_repair(command, prepared):
    """Stage selected actions, revalidate them, then delete staged entries."""
    root = prepared["root"]
    selected = prepared["selected"]
    stale = command._stale_actions(root, selected)
    if stale:
        return command._repair_error(
            WorkspaceAuditError(
                "workspace_changed_since_audit",
                "The workspace changed immediately before staging.",
                {
                    "stale_actions": stale,
                    "remediation": "Run auditWorkspace again.",
                },
            )
        )

    stage = root / ".qzx-repair-stage-{}".format(uuid.uuid4().hex)
    staged = []
    try:
        _stage_selected(command, root, selected, stage, staged)
    except Exception as exc:
        return _staging_failure(command, prepared, stage, staged, exc)

    deleted, cleanup_failure = _delete_staged_entries(staged)
    if cleanup_failure is not None:
        return _cleanup_incomplete(
            prepared,
            stage,
            staged,
            deleted,
            cleanup_failure,
        )
    try:
        stage.rmdir()
    except OSError as exc:
        return _stage_directory_cleanup_failure(
            prepared,
            stage,
            deleted,
            exc,
        )
    return _applied_result(prepared, deleted)


def _stage_selected(command, root, selected, stage, staged):
    stage.mkdir(mode=0o700)
    for index, action in enumerate(selected):
        reason = verify_action_fingerprint(root, action)
        if reason:
            raise WorkspaceAuditError(
                "workspace_changed_during_repair",
                "Action '{}' changed before it could be staged.".format(
                    action["id"]
                ),
                {
                    "action_id": action["id"],
                    "path": action["path"],
                    "reason": reason,
                },
            )
        original = root.joinpath(*PurePosixPath(action["path"]).parts)
        staged_path = stage / "{:04d}-{}".format(index, action["id"])
        command._rename_operation(original, staged_path)
        staged.append(
            {
                "action": action,
                "original": original,
                "staged": staged_path,
            }
        )


def _staging_failure(command, prepared, stage, staged, exc):
    rollback_failures, stage_cleanup_failure = command._rollback_staged(
        staged,
        stage,
    )
    details = {
        "path": str(prepared["root"]),
        "plan_id": prepared["plan"]["plan_id"],
        "staged_actions": [item["action"]["id"] for item in staged],
        "rollback_failures": rollback_failures,
        "workspace_restored": not rollback_failures,
    }
    if stage_cleanup_failure is not None:
        details["stage_cleanup_failure"] = stage_cleanup_failure
    if stage.exists():
        details["recovery_stage"] = str(stage)
    error_code, error = _staging_error(exc, details)
    return {
        "success": False,
        "status": (
            "rolled_back" if not rollback_failures else "recovery_required"
        ),
        "error_code": error_code,
        "error": error,
        "message": _staging_failure_message(rollback_failures),
        "details": details,
    }


def _staging_error(exc, details):
    if isinstance(exc, WorkspaceAuditError):
        details.update(exc.details)
        return exc.code, str(exc)
    return "workspace_staging_failed", "{}: {}".format(
        type(exc).__name__,
        exc,
    )


def _staging_failure_message(rollback_failures):
    message = "Workspace repair was aborted during staging. "
    if not rollback_failures:
        return message + "Every staged entry was restored."
    return (
        message
        + "Some entries could not be restored automatically; use "
        "recovery_stage or the reported safety backup."
    )


def _delete_staged_entries(staged):
    deleted = []
    for item in staged:
        try:
            if item["staged"].is_dir():
                shutil.rmtree(item["staged"])
            else:
                item["staged"].unlink()
            deleted.append(item["action"])
        except Exception as exc:
            return deleted, {
                "action_id": item["action"]["id"],
                "path": item["action"]["path"],
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
    return deleted, None


def _cleanup_incomplete(
    prepared,
    stage,
    staged,
    deleted,
    cleanup_failure,
):
    remaining = [
        {
            "action_id": item["action"]["id"],
            "original_path": str(item["original"]),
            "staged_path": str(item["staged"]),
        }
        for item in staged
        if item["staged"].exists()
    ]
    return {
        "success": False,
        "status": "cleanup_incomplete",
        "error_code": "workspace_cleanup_incomplete",
        "error": cleanup_failure["error"],
        "message": (
            "All selected entries were isolated from the workspace, but "
            "staging cleanup was incomplete. Recover remaining entries from "
            "the stage or the reported safety backup."
        ),
        "details": {
            "path": str(prepared["root"]),
            "plan_id": prepared["plan"]["plan_id"],
            "recovery_stage": str(stage),
            "deleted_actions": deleted,
            "remaining_staged_entries": remaining,
            "cleanup_failure": cleanup_failure,
        },
    }


def _stage_directory_cleanup_failure(prepared, stage, deleted, exc):
    return {
        "success": False,
        "status": "cleanup_incomplete",
        "error_code": "staging_directory_cleanup_failed",
        "error": "{}: {}".format(type(exc).__name__, exc),
        "message": (
            "The selected cleanup actions were applied, but QZX could not "
            "remove the now-empty staging directory."
        ),
        "details": {
            "path": str(prepared["root"]),
            "plan_id": prepared["plan"]["plan_id"],
            "recovery_stage": str(stage),
            "deleted_actions": deleted,
            "remaining_staged_entries": [],
            "workspace_cleanup_applied": True,
        },
    }


def _applied_result(prepared, deleted):
    recovered_bytes = sum(
        action.get("size_bytes", 0)
        for action in deleted
    )
    return {
        "success": True,
        "status": "applied",
        "message": (
            "Applied {} reviewed workspace cleanup action(s), recovering "
            "{} byte(s)."
        ).format(len(deleted), recovered_bytes),
        "details": {
            "path": str(prepared["root"]),
            "plan_file": str(prepared["plan_path"]),
            "plan_id": prepared["plan"]["plan_id"],
            "dry_run_mode": False,
            "workspace_backup_required": True,
            "applied_actions": deleted,
            "recovered_bytes": recovered_bytes,
            "staging_removed": True,
        },
    }


def rollback_staged(command, staged, stage):
    """Restore staged entries in reverse order after a staging failure."""
    failures = []
    for item in reversed(staged):
        try:
            if os.path.lexists(item["original"]):
                raise FileExistsError(
                    "Original path was recreated during rollback."
                )
            command._rename_operation(item["staged"], item["original"])
        except Exception as exc:
            failures.append(
                {
                    "action_id": item["action"]["id"],
                    "original_path": str(item["original"]),
                    "staged_path": str(item["staged"]),
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
    return failures, _cleanup_stage_after_rollback(stage, failures)


def _cleanup_stage_after_rollback(stage, failures):
    if failures or not stage.exists():
        return None
    try:
        stage.rmdir()
        return None
    except OSError as exc:
        return {
            "path": str(stage),
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
