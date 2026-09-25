"""Build public auditWorkspace responses from workspace plans."""


def _audit_message(plan, saved_path):
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
    return message


def build_audit_result(plan, saved_path=None):
    """Return the stable public result contract for a completed audit attempt."""
    return {
        "success": plan["scan_complete"],
        "status": "complete" if plan["scan_complete"] else "incomplete",
        "message": _audit_message(plan, saved_path),
        "details": {
            "path": plan["root"],
            "workspace_unchanged": True,
            "plan_file": saved_path,
            "plan": plan,
        },
    }
