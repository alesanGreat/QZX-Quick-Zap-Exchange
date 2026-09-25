#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Apply explicitly selected actions from a fingerprinted workspace audit."""

from __future__ import annotations

import os
from pathlib import Path, PurePosixPath
from typing import ClassVar

from qzx.commands.file._workspace_repair_apply import (
    apply_prepared_repair,
    rollback_staged,
)
from qzx.commands.file._workspace_repair_plan import load_repair_plan
from qzx.commands.file._workspace_repair_prepare import (
    prepare_repair,
    preview_repair_result,
)
from qzx.core.command_base import CommandBase
from qzx.core.workspace_audit import (
    WorkspaceAuditError,
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

    result_schema: ClassVar[dict[str, object]] = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "message": {"type": "string"},
            "status": {
                "type": "string",
                "enum": [
                    "preview",
                    "applied",
                    "rolled_back",
                    "recovery_required",
                    "cleanup_incomplete",
                ],
            },
            "error_code": {"type": "string"},
            "error": {"type": "string"},
            "details": {
                "type": "object",
                "additionalProperties": True,
            },
        },
        "additionalProperties": True,
    }

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
        return prepare_repair(
            self,
            path=path,
            plan_file=plan_file,
            action_ids=action_ids,
            require_selected=require_selected,
            verify_all_when_unselected=verify_all_when_unselected,
        )

    @staticmethod
    def _load_plan(plan_file):
        return load_repair_plan(plan_file)

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
        return preview_repair_result(
            prepared,
            dry_run=dry_run,
            apply=apply,
        )

    def _apply_prepared(self, prepared):
        return apply_prepared_repair(self, prepared)

    def _rollback_staged(self, staged, stage):
        return rollback_staged(self, staged, stage)

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
