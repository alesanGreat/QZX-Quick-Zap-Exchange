"""Human-readable report for ``diagnoseProject``."""

from textwrap import fill


def _single_line(value):
    printable = "".join(character if character.isprintable() else " " for character in str(value))
    return " ".join(printable.split())


def _briefing(details):
    dependencies, git, scan = details["dependencies"], details["version_control"], details["file_scan"]
    package_count, manifest_count = dependencies["unique_declared_package_count"], dependencies["manifest_count"]
    lines = [
        "PROJECT BRIEFING", "Path: " + _single_line(details["path"]),
        "Technologies: " + _single_line(", ".join(details["technologies"]) or "Not identified"),
        f"Dependencies: {package_count} unique declared {'package' if package_count == 1 else 'packages'} in {manifest_count} {'manifest' if manifest_count == 1 else 'manifests'}",
    ]
    if git["status"] == "inspected":
        state = "clean working tree" if git["clean"] else f"{git['changed_count']} tracked changes, {git['untracked_count']} untracked paths"
        lines.append(f"Git: {_single_line(git['branch'])}; {state}")
    elif git["status"] == "not_repository":
        lines.append("Git: repository not detected")
    else:
        lines.append("Git: state unavailable; do not assume a clean working tree")
    coverage = "complete" if scan["scan_complete"] else "PARTIAL (limit reached)"
    if scan["error_count"]:
        coverage += f"; {scan['error_count']} metadata reads failed"
    lines.append(f"File scan: {scan['scanned_file_count']} files; {coverage}; {scan['large_file_count']} larger than {scan['large_file_threshold_formatted']}")
    return lines


def _findings(summary):
    statuses = {"critical": "Critical findings", "attention": "Needs attention", "review": "Review recommended", "no_issues_observed": "No issues observed"}
    lines = ["", "FINDINGS - " + statuses[summary["status"]], f"{summary['issue_count']} issues; {summary['informational_count']} informational observations"]
    priority = {"high": 0, "medium": 1, "low": 2, "info": 3}
    issues = sorted(summary["issues"], key=lambda issue: priority[issue["severity"]])
    for number, issue in enumerate(issues, 1):
        heading = f"{number}. [{issue['severity'].upper()}] {_single_line(issue['title'])}"
        lines.append(fill(heading, width=88, subsequent_indent="   "))
        lines.append(fill("Next: " + _single_line(issue["remediation"]), width=88, initial_indent="   ", subsequent_indent="   "))
    if not issues:
        lines.append("No issues were observed within this inspection's scope.")
    return lines


def _validation(details):
    labels = {"tests": "Tests", "lint": "Lint", "type_checking": "Type checks", "build": "Build"}
    lines = ["", "VALIDATION - DISCOVERED, NOT RUN"]
    for key, label in labels.items():
        configured = details["validation"][key]["configured"]
        lines.append(f"{label}: {'configured, not run' if configured else 'not detected'}")
    commands = details["summary"]["verification"]["suggested_commands"]
    if commands:
        lines.extend(["", "Review the project scripts before running these commands.", "Run from: " + _single_line(details["path"])])
        lines.extend("  " + _single_line(command) for command in commands)
    else:
        lines.append("No validation command was discovered.")
    lines.extend(["", "Release readiness: NOT ASSESSED. Inspection is not a test run.", "Use --json for the full structured evidence and finding descriptions."])
    return lines


def render_report(details):
    return "\n".join([*_briefing(details), *_findings(details["summary"]), *_validation(details)])
