#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Audit a workspace and emit a deterministic, non-mutating repair plan."""

from __future__ import annotations

import json
import os
from pathlib import Path, PurePosixPath
import tempfile

from qzx.core.command_base import CommandBase
from qzx.core.workspace_audit import (
    DEFAULT_MAX_FILES,
    MAX_PLAN_BYTES,
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

        summary = plan["summary"]
        if plan["scan_complete"]:
            message = (
                "Workspace audit complete: {} executable cleanup action(s) and "
                "{} review-only finding(s), totaling {} recoverable byte(s)."
            ).format(
                summary["executable_actions"],
                summary["review_only_actions"],
                summary["recoverable_bytes"],
            )
        else:
            message = (
                "Workspace audit stopped without a complete scan. Its plan is "
                "diagnostic only and repairWorkspace will refuse to apply it."
            )
        if saved_path:
            message += " Plan saved to '{}'.".format(saved_path)

        return {
            "success": plan["scan_complete"],
            "status": "complete" if plan["scan_complete"] else "incomplete",
            "message": message,
            "details": {
                "path": plan["root"],
                "workspace_unchanged": True,
                "plan_file": saved_path,
                "plan": plan,
            },
        }

    @staticmethod
    def _save_new_plan(plan, plan_file):
        destination = Path(plan_file).expanduser()
        destination = Path(os.path.abspath(os.fspath(destination)))
        if os.path.lexists(destination):
            raise WorkspaceAuditError(
                "plan_file_exists",
                "Plan file '{}' already exists and was not overwritten.".format(
                    destination
                ),
                {
                    "plan_file": str(destination),
                    "remediation": "Choose a new plan filename.",
                },
            )
        parent = destination.parent
        if not parent.is_dir():
            raise WorkspaceAuditError(
                "plan_parent_not_found",
                "Plan parent directory '{}' does not exist.".format(parent),
                {"plan_file": str(destination)},
            )
        if AuditWorkspaceCommand._plan_file_would_be_deleted(plan, destination):
            raise WorkspaceAuditError(
                "plan_file_inside_cleanup_target",
                "Plan file '{}' would be inside a proposed cleanup target.".format(
                    destination
                ),
                {
                    "plan_file": str(destination),
                    "remediation": "Save the plan outside every proposed deletion.",
                },
            )

        payload = (
            json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
        if len(payload) > MAX_PLAN_BYTES:
            raise WorkspaceAuditError(
                "plan_file_too_large",
                (
                    "Generated plan is {} bytes; repairWorkspace accepts at "
                    "most {} bytes."
                ).format(len(payload), MAX_PLAN_BYTES),
                {
                    "plan_file": str(destination),
                    "plan_size_bytes": len(payload),
                    "max_plan_bytes": MAX_PLAN_BYTES,
                    "remediation": (
                        "Reduce max_files or audit fewer categories before "
                        "saving another plan."
                    ),
                },
            )
        temporary_name = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                prefix=".qzx-plan-",
                suffix=".tmp",
                dir=parent,
                delete=False,
            ) as temporary:
                temporary_name = temporary.name
                temporary.write(payload)
                temporary.flush()
                os.fsync(temporary.fileno())
            # A hard link publishes the completed inode atomically and fails if
            # another process created the requested destination in the meantime.
            os.link(temporary_name, destination)
        finally:
            if temporary_name and os.path.lexists(temporary_name):
                os.unlink(temporary_name)
        return str(destination)

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
