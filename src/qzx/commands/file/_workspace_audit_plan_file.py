"""Persist auditWorkspace plans safely without overwriting existing files."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

from qzx.core.workspace_audit import MAX_PLAN_BYTES, WorkspaceAuditError


def _validated_destination(plan, plan_file, would_be_deleted):
    destination = Path(os.path.abspath(os.fspath(Path(plan_file).expanduser())))
    if os.path.lexists(destination):
        raise WorkspaceAuditError(
            "plan_file_exists",
            "Plan file '{}' already exists and was not overwritten.".format(destination),
            {
                "plan_file": str(destination),
                "remediation": "Choose a new plan filename.",
            },
        )
    if not destination.parent.is_dir():
        raise WorkspaceAuditError(
            "plan_parent_not_found",
            "Plan parent directory '{}' does not exist.".format(destination.parent),
            {"plan_file": str(destination)},
        )
    if would_be_deleted(plan, destination):
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
    return destination


def _serialized_plan(plan, destination):
    payload = (
        json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    if len(payload) > MAX_PLAN_BYTES:
        raise WorkspaceAuditError(
            "plan_file_too_large",
            (
                "Generated plan is {} bytes; repairWorkspace accepts at most "
                "{} bytes."
            ).format(len(payload), MAX_PLAN_BYTES),
            {
                "plan_file": str(destination),
                "plan_size_bytes": len(payload),
                "max_plan_bytes": MAX_PLAN_BYTES,
                "remediation": (
                    "Reduce max_files or audit fewer categories before saving "
                    "another plan."
                ),
            },
        )
    return payload


def _publish_payload(destination, payload):
    temporary_name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=".qzx-plan-",
            suffix=".tmp",
            dir=destination.parent,
            delete=False,
        ) as temporary:
            temporary_name = temporary.name
            temporary.write(payload)
            temporary.flush()
            os.fsync(temporary.fileno())
        # Publish the completed inode atomically and fail if the destination
        # appeared concurrently.
        os.link(temporary_name, destination)
    finally:
        if temporary_name and os.path.lexists(temporary_name):
            os.unlink(temporary_name)


def save_new_plan(plan, plan_file, would_be_deleted):
    """Validate and atomically publish a new audit plan file."""
    destination = _validated_destination(plan, plan_file, would_be_deleted)
    payload = _serialized_plan(plan, destination)
    _publish_payload(destination, payload)
    return str(destination)
