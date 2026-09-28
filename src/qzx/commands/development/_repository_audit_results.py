"""Shared result mutation helpers for repository-audit phases."""


def record_finding(results, severity, category, message):
    results["summary"]["findings"].append(
        {"severity": severity, "category": category, "message": message}
    )


def record_scan_issue(results, relative, operation, error, **details):
    issue = {"operation": operation, "error": str(error), **details}
    if relative is not None:
        issue["path"] = relative
    results["scan_issues"].append(issue)
