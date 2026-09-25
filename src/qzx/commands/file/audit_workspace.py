#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Audit a workspace and emit a deterministic, non-mutating repair plan."""

from __future__ import annotations

import os
from pathlib import Path, PurePosixPath

from qzx.commands.file._workspace_audit_plan_file import save_new_plan
from qzx.commands.file._workspace_audit_response import build_audit_result
from qzx.core.command_base import CommandBase
from qzx.core.workspace_audit import (
    DEFAULT_MAX_FILES,
    WorkspaceAuditError,
    build_workspace_plan,
)


class AuditWorkspaceCommand(CommandBase):
    """Describe cleanup candidates without changing the audited workspace."""

    name = "auditWorkspace"
    description = (
        "Builds a deterministic, fingerprinted workspace cleanup plan without "
        "altering workspace contents"
    )
    category = "file"

    parameters = [
        {
            "name": "path",
            "description": "Workspace directory to audit",
            "required": False,
            "default": ".",
            "type": "str",
        },
        {
            "name": "categories",
            "description": (
                "Comma-separated categories: build, temp, artifacts, "
                "duplicates, reorganizations"
            ),
            "required": False,
            "default": "build,temp,artifacts,duplicates,reorganizations",
            "type": "str",
        },
        {
            "name": "max_files",
            "description": "Maximum number of non-directory entries to inspect",
            "required": False,
            "default": DEFAULT_MAX_FILES,
            "type": "int",
        },
        {
            "name": "plan_file",
            "description": (
                "Optional new JSON file in which to save the plan; existing "
                "files are never overwritten"
            ),
            "required": False,
            "default": None,
            "type": "str",
        },
    ]

    examples = [
        {
            "command": "qzx auditWorkspace .",
            "description": "Inspect the current workspace without writing files",
        },
        {
            "command": (
                "qzx auditWorkspace . --categories build,temp,duplicates "
                "--plan-file qzx-repair-plan.json"
            ),
            "description": "Save a plan that repairWorkspace can validate later",
        },
    ]

    def execute(
        self,
        path=".",
        categories="build,temp,artifacts,duplicates,reorganizations",
        max_files=DEFAULT_MAX_FILES,
        plan_file=None,
    ):
        try:
            plan = build_workspace_plan(
                path=path,
                categories=categories,
                max_files=max_files,
            )
        except WorkspaceAuditError as exc:
            return self._audit_error(exc)
        except OSError as exc:
            return {
                "success": False,
                "error_code": "workspace_audit_failed",
                "error": "{}: {}".format(type(exc).__name__, exc),
                "message": "The workspace could not be audited safely.",
                "details": {"path": os.path.abspath(os.fspath(path))},
            }

        saved_path = None
        if plan_file not in {None, ""}:
            try:
                saved_path = self._save_new_plan(plan, plan_file)
            except WorkspaceAuditError as exc:
                return self._audit_error(exc, plan=plan)
            except OSError as exc:
                return {
                    "success": False,
                    "error_code": "plan_write_failed",
                    "error": "{}: {}".format(type(exc).__name__, exc),
                    "message": (
                        "The workspace was audited, but its plan file could not "
                        "be saved. Nothing in the workspace was changed."
                    ),
                    "details": {
                        "path": plan["root"],
                        "plan": plan,
                        "plan_file": os.path.abspath(os.fspath(plan_file)),
                    },
                }

        return build_audit_result(plan, saved_path)

    @staticmethod
    def _save_new_plan(plan, plan_file):
        return save_new_plan(
            plan,
            plan_file,
            AuditWorkspaceCommand._plan_file_would_be_deleted,
        )

    @staticmethod
    def _plan_file_would_be_deleted(plan, destination):
        root = Path(plan["root"])
        try:
            relative = destination.relative_to(root).as_posix()
        except ValueError:
            return False
        relative_path = PurePosixPath(relative)
        for action in plan["actions"]:
            if not action["executable"]:
                continue
            action_path = PurePosixPath(action["path"])
            if relative_path == action_path:
                return True
            if (
                action["kind"] == "delete_directory"
                and action_path in relative_path.parents
            ):
                return True
        return False

    @staticmethod
    def _audit_error(exc, plan=None):
        details = dict(exc.details)
        if plan is not None:
            details["plan"] = plan
        return {
            "success": False,
            "error_code": exc.code,
            "error": str(exc),
            "message": "{} Nothing in the workspace was changed.".format(exc),
            "details": details,
        }
