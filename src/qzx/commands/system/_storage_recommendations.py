"""Evidence-based next steps without treating size or duplication as deletion approval."""

from __future__ import annotations


_CAPACITY_ACTIONS = {
    "critical": (
        "high", "Review the largest files and confirmed duplicate groups before adding more data."
    ),
    "attention": (
        "medium", "Review high-impact storage consumers before the filesystem becomes constrained."
    ),
}


def storage_recommendations(assessment, scope, coverage):
    recommendations = _capacity_recommendations(assessment)
    if coverage["partial"]:
        recommendations.append({
            "priority": "review",
            "action": "Inspect the warning paths and repeat only the required scope after access problems or concurrent writes are resolved.",
            "reason": "Partial evidence cannot establish that unreadable or changed files contain no duplicates.",
        })
    recommendations.append(_large_file_recommendation(assessment, scope))
    recommendations.extend(_duplicate_recommendations(assessment, coverage))
    recommendations.append({
        "priority": "info",
        "action": "Use getDiskHealth separately only when hardware health is relevant; capacity pressure does not imply a failing disk.",
        "reason": "S.M.A.R.T. health and filesystem capacity are separate diagnostic questions.",
    })
    return recommendations


def _capacity_recommendations(assessment):
    action = _CAPACITY_ACTIONS.get(assessment["capacity_status"])
    if action is None:
        return []
    priority, text = action
    return [{
        "priority": priority, "action": text,
        "reason": f"The target filesystem is {assessment['percent_used']:g}% used.",
    }]


def _large_file_recommendation(assessment, scope):
    threshold, depth = scope["min_file_size"], scope["max_depth"]
    if assessment["large_files_matched"]:
        return {
            "priority": "review",
            "action": "Inspect the returned large-file paths and decide which are intentional; size alone is never a deletion signal.",
            "reason": f"Files at or above {threshold} were found within depth {depth}.",
        }
    return {
        "priority": "info",
        "action": "If storage is still constrained, lower --min-file-size or increase --max-depth to broaden the evidence.",
        "reason": f"No files met the {threshold} threshold in the scanned scope.",
    }


def _duplicate_recommendations(assessment, coverage):
    status = coverage["probe_status"]["duplicates"]
    groups = assessment["duplicate_groups"]
    if status in {"ok", "partial"} and groups:
        return [{
            "priority": "review",
            "action": "Review each duplicate group and keep at least one intentional copy before removing anything manually.",
            "reason": (
                f"Byte-for-byte verification found {groups} group(s) with "
                f"{assessment['confirmed_reclaimable_readable']} of redundant logical content; "
                "actual physical disk savings were not measured."
            ),
        }]
    if status == "skipped":
        return [{
            "priority": "info",
            "action": "Run again with --include-duplicates true when duplicate content is worth checking.",
            "reason": "Duplicate hashing was explicitly skipped for this run.",
        }]
    return []
