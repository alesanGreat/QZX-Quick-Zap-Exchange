"""Preparation and preview workflow for repairWorkspace."""

from __future__ import annotations

import os

from qzx.core.workspace_audit import (
    WorkspaceAuditError,
    resolve_workspace_root,
    validate_plan_integrity,
)


def prepare_repair(
    command,
    *,
    path,
    plan_file,
    action_ids,
    require_selected,
    verify_all_when_unselected,
):
    """Validate a saved plan and select safe executable actions."""
    root, plan_path, plan = _validated_plan(command, path, plan_file)
    requested_ids = command._parse_action_ids(action_ids)
    executable, selected = _selected_actions(
        plan,
        requested_ids,
        require_selected,
    )

    command._reject_overlapping_actions(selected)
    command._reject_plan_inside_selection(root, plan_path, selected)
    _verify_action_fingerprints(
        command,
        root,
        plan,
        selected,
        executable,
        verify_all_when_unselected,
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


def _validated_plan(command, path, plan_file):
    root = resolve_workspace_root(path)
    plan_path, plan = command._load_plan(plan_file)
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
    _require_complete_plan(plan)
    return root, plan_path, plan


def _require_complete_plan(plan):
    if plan["scan_complete"]:
        return
    raise WorkspaceAuditError(
        "incomplete_plan_refused",
        "An incomplete workspace audit plan cannot be applied.",
        {
            "plan_id": plan["plan_id"],
            "scan_errors": plan.get("scan_errors", []),
            "remediation": (
                "Run auditWorkspace again with sufficient access and limits."
            ),
        },
    )


def _selected_actions(plan, requested_ids, require_selected):
    executable = {
        action["id"]: action
        for action in plan["actions"]
        if action["executable"]
    }
    all_actions = {action["id"]: action for action in plan["actions"]}
    _reject_unknown_actions(plan, requested_ids, all_actions)
    _reject_review_only_actions(requested_ids, executable)

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
    return executable, selected


def _reject_unknown_actions(plan, requested_ids, all_actions):
    unknown = [
        action_id
        for action_id in requested_ids
        if action_id not in all_actions
    ]
    if not unknown:
        return
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


def _reject_review_only_actions(requested_ids, executable):
    review_only = [
        action_id
        for action_id in requested_ids
        if action_id not in executable
    ]
    if not review_only:
        return
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


def _verify_action_fingerprints(
    command,
    root,
    plan,
    selected,
    executable,
    verify_all_when_unselected,
):
    actions_to_verify = (
        selected
        if selected or not verify_all_when_unselected
        else list(executable.values())
    )
    stale = command._stale_actions(root, actions_to_verify)
    if not stale:
        return
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


def preview_repair_result(prepared, *, dry_run, apply):
    """Render the stable non-mutating repairWorkspace preview."""
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
        message += (
            " Add --apply after selecting action IDs to authorize mutation."
        )
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
