#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Apply explicitly selected actions from a fingerprinted workspace audit."""

from __future__ import annotations

import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import uuid

from qzx.core.command_base import CommandBase
from qzx.core.workspace_audit import (
    MAX_PLAN_BYTES,
    WorkspaceAuditError,
    resolve_workspace_root,
    validate_plan_integrity,
    verify_action_fingerprint,
)


class RepairWorkspaceCommand(CommandBase):
    """Apply a reviewed cleanup plan through staging and revalidation."""

    name = "repairWorkspace"
    description = (
        "Validates a saved auditWorkspace plan and applies only explicitly "
        "selected, unchanged cleanup actions"
    )
    category = "file"
    requires_explicit_approval = True
    backup_target_parameter = "path"

    parameters = [
        {
            "name": "path",
            "description": "Workspace directory that the saved plan audits",
            "required": False,
            "default": ".",
            "type": "str",
        },
        {
            "name": "plan_file",
            "description": "JSON plan created by auditWorkspace",
            "required": False,
            "default": None,
            "type": "str",
        },
        {
            "name": "action_ids",
            "description": (
                "Comma-separated executable action IDs reviewed by the operator"
            ),
            "required": False,
            "default": None,
            "type": "str",
        },
        {
            "name": "dry_run",
            "description": "Validate and preview without changing the workspace",
            "required": False,
            "default": True,
            "type": "bool",
        },
        {
            "name": "apply",
            "description": (
                "Explicitly authorize selected actions; requires dry_run=false"
            ),
            "required": False,
            "default": False,
            "type": "bool",
        },
    ]

    examples = [
        {
            "command": "qzx repairWorkspace . --plan-file qzx-repair-plan.json",
            "description": "Validate the saved plan and list its executable actions",
        },
        {
            "command": (
                "qzx repairWorkspace . --plan-file qzx-repair-plan.json "
                "--action-ids act-123,act-456 --dry-run false --apply"
            ),
            "description": (
                "Back up the workspace, revalidate both actions, then apply them"
            ),
        },
    ]

    def __init__(self, rename_operation=None):
        """Accept an explicit filesystem boundary for deterministic testing."""
        self._rename_operation = rename_operation or os.rename

    def validate_safety_backup_target(self, target, values):
        """Validate the exact live plan before spending time on a backup."""
        try:
            self._prepare(
                path=target,
                plan_file=values.get("plan_file"),
                action_ids=values.get("action_ids"),
                require_selected=True,
                verify_all_when_unselected=False,
            )
        except WorkspaceAuditError as exc:
            return self._repair_error(exc)
        return None

    def execute(
        self,
        path=".",
        plan_file=None,
        action_ids=None,
        dry_run=True,
        apply=False,
    ):
        parsed_dry_run = self._strict_bool(dry_run, "dry_run")
        if isinstance(parsed_dry_run, dict):
            return parsed_dry_run
        parsed_apply = self._strict_bool(apply, "apply")
        if isinstance(parsed_apply, dict):
            return parsed_apply
        live = not parsed_dry_run and parsed_apply

        try:
            prepared = self._prepare(
                path=path,
                plan_file=plan_file,
                action_ids=action_ids,
                require_selected=live,
                verify_all_when_unselected=not live,
            )
        except WorkspaceAuditError as exc:
            return self._repair_error(exc)

        if not live:
            return self._preview_result(
                prepared,
                dry_run=parsed_dry_run,
                apply=parsed_apply,
            )
        return self._apply_prepared(prepared)

    def _prepare(
        self,
        *,
        path,
        plan_file,
        action_ids,
        require_selected,
        verify_all_when_unselected,
    ):
        root = resolve_workspace_root(path)
        plan_path, plan = self._load_plan(plan_file)
        validate_plan_integrity(plan)

        plan_root = resolve_workspace_root(plan["root"])
        if os.path.normcase(str(root)) != os.path.normcase(str(plan_root)):
            raise WorkspaceAuditError(
                "plan_root_mismatch",
                "The plan audits '{}', not requested workspace '{}'.".format(
                    plan_root,
                    root,
                ),
                {
                    "requested_root": str(root),
                    "plan_root": str(plan_root),
                    "plan_id": plan["plan_id"],
                },
            )
        if not plan["scan_complete"]:
            raise WorkspaceAuditError(
                "incomplete_plan_refused",
                "An incomplete workspace audit plan cannot be applied.",
                {
                    "plan_id": plan["plan_id"],
                    "scan_errors": plan.get("scan_errors", []),
                    "remediation": "Run auditWorkspace again with sufficient access and limits.",
                },
            )

        requested_ids = self._parse_action_ids(action_ids)
        executable = {
            action["id"]: action
            for action in plan["actions"]
            if action["executable"]
        }
        all_actions = {action["id"]: action for action in plan["actions"]}

        unknown = [action_id for action_id in requested_ids if action_id not in all_actions]
        if unknown:
            raise WorkspaceAuditError(
                "unknown_action_ids",
                "The plan does not contain action ID(s): {}.".format(
                    ", ".join(unknown)
                ),
                {
                    "unknown_action_ids": unknown,
                    "plan_id": plan["plan_id"],
                },
            )
        review_only = [
            action_id for action_id in requested_ids if action_id not in executable
        ]
        if review_only:
            raise WorkspaceAuditError(
                "review_action_refused",
                "Review-only action(s) cannot be applied: {}.".format(
                    ", ".join(review_only)
                ),
                {
                    "review_only_action_ids": review_only,
                    "remediation": (
                        "Inspect and perform any reorganization manually with a "
                        "tool designed for that specific change."
                    ),
                },
            )

        selected = [executable[action_id] for action_id in requested_ids]
        if require_selected and not selected:
            raise WorkspaceAuditError(
                "action_ids_required",
                "Live repair requires at least one explicit action ID.",
                {
                    "plan_id": plan["plan_id"],
                    "available_action_ids": sorted(executable),
                },
            )
        self._reject_overlapping_actions(selected)
        self._reject_plan_inside_selection(root, plan_path, selected)

        actions_to_verify = (
            selected
            if selected or not verify_all_when_unselected
            else list(executable.values())
        )
        stale = self._stale_actions(root, actions_to_verify)
        if stale:
            raise WorkspaceAuditError(
                "workspace_changed_since_audit",
                "{} selected or available action(s) no longer match the plan.".format(
                    len(stale)
                ),
                {
                    "plan_id": plan["plan_id"],
                    "stale_actions": stale,
                    "remediation": "Discard this plan and run auditWorkspace again.",
                },
            )
        return {
            "root": root,
            "plan_path": plan_path,
            "plan": plan,
            "selected": selected,
            "executable": list(executable.values()),
            "review_only": [
                action for action in plan["actions"] if not action["executable"]
            ],
        }

    @staticmethod
    def _load_plan(plan_file):
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
        plan_path = Path(plan_file).expanduser()
        plan_path = Path(os.path.abspath(os.fspath(plan_path)))
        if not os.path.lexists(plan_path):
            raise WorkspaceAuditError(
                "plan_file_not_found",
                "Plan file '{}' does not exist.".format(plan_path),
                {"plan_file": str(plan_path)},
            )
        if os.path.islink(plan_path) or (
            hasattr(os.path, "isjunction") and os.path.isjunction(plan_path)
        ):
            raise WorkspaceAuditError(
                "plan_file_link_refused",
                "Plan file '{}' is a symbolic link or junction.".format(plan_path),
                {"plan_file": str(plan_path)},
            )
        before_open = os.stat(plan_path, follow_symlinks=False)
        if not stat.S_ISREG(before_open.st_mode):
            raise WorkspaceAuditError(
                "plan_file_not_regular",
                "Plan path '{}' is not a regular file.".format(plan_path),
                {"plan_file": str(plan_path)},
            )
        size = before_open.st_size
        if size > MAX_PLAN_BYTES:
            raise WorkspaceAuditError(
                "plan_file_too_large",
                "Plan file is {} bytes; the limit is {} bytes.".format(
                    size,
                    MAX_PLAN_BYTES,
                ),
                {"plan_file": str(plan_path), "size_bytes": size},
            )
        descriptor = None
        try:
            flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
            flags |= getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(plan_path, flags)
            opened = os.fstat(descriptor)
            after_open = os.stat(plan_path, follow_symlinks=False)
            if not stat.S_ISREG(opened.st_mode) or (
                (before_open.st_dev, before_open.st_ino)
                != (opened.st_dev, opened.st_ino)
                or (after_open.st_dev, after_open.st_ino)
                != (opened.st_dev, opened.st_ino)
            ):
                raise WorkspaceAuditError(
                    "plan_file_changed_during_read",
                    "Plan file '{}' changed while it was being opened.".format(
                        plan_path
                    ),
                    {"plan_file": str(plan_path)},
                )
            with os.fdopen(descriptor, "r", encoding="utf-8") as handle:
                descriptor = None
                document = json.load(handle)
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

        plan = document
        if (
            isinstance(document, dict)
            and isinstance(document.get("details"), dict)
            and isinstance(document["details"].get("plan"), dict)
        ):
            plan = document["details"]["plan"]
        return plan_path, plan

    @staticmethod
    def _parse_action_ids(value):
        if value in {None, ""}:
            return []
        if isinstance(value, str):
            identifiers = [item.strip() for item in value.split(",") if item.strip()]
        elif isinstance(value, (list, tuple)):
            identifiers = [str(item).strip() for item in value if str(item).strip()]
        else:
            raise WorkspaceAuditError(
                "invalid_action_ids",
                "action_ids must be comma-separated text or a list.",
                {"received_type": type(value).__name__},
            )
        if len(identifiers) != len(set(identifiers)):
            raise WorkspaceAuditError(
                "duplicate_action_ids",
                "Each action ID may be selected only once.",
                {"action_ids": identifiers},
            )
        return identifiers

    @staticmethod
    def _reject_overlapping_actions(actions):
        paths = [
            (action, PurePosixPath(action["path"]))
            for action in actions
        ]
        overlaps = []
        for index, (first_action, first_path) in enumerate(paths):
            for second_action, second_path in paths[index + 1 :]:
                if first_path == second_path:
                    overlaps.append([first_action["id"], second_action["id"]])
                elif (
                    first_action["kind"] == "delete_directory"
                    and first_path in second_path.parents
                ):
                    overlaps.append([first_action["id"], second_action["id"]])
                elif (
                    second_action["kind"] == "delete_directory"
                    and second_path in first_path.parents
                ):
                    overlaps.append([first_action["id"], second_action["id"]])
        if overlaps:
            raise WorkspaceAuditError(
                "overlapping_actions_refused",
                "Selected workspace actions overlap and cannot be staged independently.",
                {"overlapping_action_ids": overlaps},
            )

    @staticmethod
    def _reject_plan_inside_selection(root, plan_path, actions):
        try:
            relative_plan = plan_path.relative_to(root)
        except ValueError:
            return
        for action in actions:
            action_path = Path(*PurePosixPath(action["path"]).parts)
            if relative_plan == action_path or (
                action["kind"] == "delete_directory"
                and action_path in relative_plan.parents
            ):
                raise WorkspaceAuditError(
                    "plan_file_selected_for_deletion",
                    "The active plan file is inside selected action '{}'.".format(
                        action["id"]
                    ),
                    {
                        "plan_file": str(plan_path),
                        "action_id": action["id"],
                        "remediation": "Save the plan outside selected cleanup targets.",
                    },
                )

    @staticmethod
    def _stale_actions(root, actions):
        stale = []
        for action in actions:
            reason = verify_action_fingerprint(root, action)
            if reason:
                stale.append(
                    {
                        "id": action["id"],
                        "path": action["path"],
                        "reason": reason,
                    }
                )
        return stale

    def _preview_result(self, prepared, *, dry_run, apply):
        selected = prepared["selected"]
        executable = prepared["executable"]
        message = (
            "Repair plan '{}' is valid and unchanged. {} executable action(s) "
            "are available; {} selected. Nothing was changed."
        ).format(
            prepared["plan"]["plan_id"],
            len(executable),
            len(selected),
        )
        if not dry_run and not apply:
            message += " Add --apply after selecting action IDs to authorize mutation."
        return {
            "success": True,
            "status": "preview",
            "message": message,
            "details": {
                "path": str(prepared["root"]),
                "plan_file": str(prepared["plan_path"]),
                "plan_id": prepared["plan"]["plan_id"],
                "dry_run_mode": True,
                "apply_requested": apply,
                "workspace_unchanged": True,
                "selected_actions": selected,
                "executable_actions": executable,
                "review_only_actions": prepared["review_only"],
            },
        }

    def _apply_prepared(self, prepared):
        root = prepared["root"]
        selected = prepared["selected"]
        # Close the ordinary audit/apply race before creating staging state.
        stale = self._stale_actions(root, selected)
        if stale:
            return self._repair_error(
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
                self._rename_operation(original, staged_path)
                staged.append(
                    {
                        "action": action,
                        "original": original,
                        "staged": staged_path,
                    }
                )
        except Exception as exc:
            rollback_failures, stage_cleanup_failure = self._rollback_staged(
                staged,
                stage,
            )
            details = {
                "path": str(root),
                "plan_id": prepared["plan"]["plan_id"],
                "staged_actions": [
                    item["action"]["id"] for item in staged
                ],
                "rollback_failures": rollback_failures,
                "workspace_restored": not rollback_failures,
            }
            if stage_cleanup_failure is not None:
                details["stage_cleanup_failure"] = stage_cleanup_failure
            if stage.exists():
                details["recovery_stage"] = str(stage)
            if isinstance(exc, WorkspaceAuditError):
                details.update(exc.details)
                error_code = exc.code
                error = str(exc)
            else:
                error_code = "workspace_staging_failed"
                error = "{}: {}".format(type(exc).__name__, exc)
            return {
                "success": False,
                "status": (
                    "rolled_back" if not rollback_failures else "recovery_required"
                ),
                "error_code": error_code,
                "error": error,
                "message": (
                    "Workspace repair was aborted during staging. "
                    + (
                        "Every staged entry was restored."
                        if not rollback_failures
                        else (
                            "Some entries could not be restored automatically; "
                            "use recovery_stage or the reported safety backup."
                        )
                    )
                ),
                "details": details,
            }

        deleted = []
        cleanup_failure = None
        for item in staged:
            try:
                if item["staged"].is_dir():
                    shutil.rmtree(item["staged"])
                else:
                    item["staged"].unlink()
                deleted.append(item["action"])
            except Exception as exc:
                cleanup_failure = {
                    "action_id": item["action"]["id"],
                    "path": item["action"]["path"],
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
                break

        if cleanup_failure is not None:
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
                    "staging cleanup was incomplete. Recover remaining entries "
                    "from the stage or the reported safety backup."
                ),
                "details": {
                    "path": str(root),
                    "plan_id": prepared["plan"]["plan_id"],
                    "recovery_stage": str(stage),
                    "deleted_actions": deleted,
                    "remaining_staged_entries": remaining,
                    "cleanup_failure": cleanup_failure,
                },
            }

        try:
            stage.rmdir()
        except OSError as exc:
            return {
                "success": False,
                "status": "cleanup_incomplete",
                "error_code": "staging_directory_cleanup_failed",
                "error": "{}: {}".format(type(exc).__name__, exc),
                "message": (
                    "The selected cleanup actions were applied, but QZX could "
                    "not remove the now-empty staging directory."
                ),
                "details": {
                    "path": str(root),
                    "plan_id": prepared["plan"]["plan_id"],
                    "recovery_stage": str(stage),
                    "deleted_actions": deleted,
                    "remaining_staged_entries": [],
                    "workspace_cleanup_applied": True,
                },
            }
        recovered_bytes = sum(action.get("size_bytes", 0) for action in deleted)
        return {
            "success": True,
            "status": "applied",
            "message": (
                "Applied {} reviewed workspace cleanup action(s), recovering "
                "{} byte(s)."
            ).format(len(deleted), recovered_bytes),
            "details": {
                "path": str(root),
                "plan_file": str(prepared["plan_path"]),
                "plan_id": prepared["plan"]["plan_id"],
                "dry_run_mode": False,
                "workspace_backup_required": True,
                "applied_actions": deleted,
                "recovered_bytes": recovered_bytes,
                "staging_removed": True,
            },
        }

    def _rollback_staged(self, staged, stage):
        failures = []
        for item in reversed(staged):
            try:
                if os.path.lexists(item["original"]):
                    raise FileExistsError(
                        "Original path was recreated during rollback."
                    )
                self._rename_operation(item["staged"], item["original"])
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
        stage_cleanup_failure = None
        if not failures and stage.exists():
            try:
                stage.rmdir()
            except OSError as exc:
                stage_cleanup_failure = {
                    "path": str(stage),
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
        return failures, stage_cleanup_failure

    def _strict_bool(self, value, name):
        if isinstance(value, bool):
            parsed = value
        elif isinstance(value, str):
            parsed = self._parse_bool(value)
        else:
            parsed = None
        if parsed is None:
            return {
                "success": False,
                "error_code": "invalid_boolean",
                "error": "{} must be true or false, got {!r}.".format(name, value),
                "message": "No workspace changes were made.",
                "details": {"parameter": name, "value": value},
            }
        return parsed

    @staticmethod
    def _repair_error(exc):
        return {
            "success": False,
            "error_code": exc.code,
            "error": str(exc),
            "message": "{} No workspace cleanup was applied.".format(exc),
            "details": dict(exc.details),
        }
