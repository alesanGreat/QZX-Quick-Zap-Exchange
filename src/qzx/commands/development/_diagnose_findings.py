"""Finding and verification summaries for ``diagnoseProject``."""

from collections import Counter


def _issue(code, severity, title, description, remediation):
    return {"code": code, "severity": severity, "title": title, "description": description, "remediation": remediation}


def _project_issues(technologies, dependencies, validation):
    issues = []
    if not technologies:
        issues.append(_issue("unknown_technology", "medium", "No supported project technology detected", "No conventional Python, Node.js, PHP, Rust, Go, C/C++, or Docker marker was found.", "Add the canonical manifest for the project or inspect the intended root directory."))
    if dependencies["parse_errors"]:
        issues.append(_issue("dependency_manifest_parse_error", "medium", "One or more dependency manifests could not be parsed", f"{len(dependencies['parse_errors'])} manifest parse error(s) prevent a complete dependency inventory.", "Correct the reported manifest syntax and run diagnoseProject again."))
    if technologies and not validation["tests"]["configured"]:
        issues.append(_issue("tests_not_configured", "medium", "No test workflow detected", "The project technology was identified, but no conventional test folder, configuration, or script was found.", "Add a maintained test workflow appropriate for the detected technology."))
    return issues


def _git_issues(state):
    if state["status"] == "not_repository":
        return [_issue("git_not_detected", "low", "Git repository not detected", "The inspected path is not inside a Git working tree.", "Use version control for maintained source projects or confirm that this directory is intentionally unversioned.")]
    if state["status"] == "unavailable":
        return [_issue("git_unavailable", "low", "Git state could not be inspected", state["reason"], "Install Git or make it available on PATH, then repeat the diagnosis.")]
    if state["status"] == "error":
        return [_issue("git_inspection_failed", "medium", "Git working-tree state could not be read", state["reason"], "Resolve the reported Git error and repeat the diagnosis; do not treat unavailable state as a clean working tree.")]
    if not state.get("clean", True):
        description = f"{state['changed_count']} tracked change(s) and {state['untracked_count']} untracked path(s) were observed."
        return [_issue("git_worktree_changed", "info", "Git working tree has local changes", description, "Review the diff and untracked paths before a release or deployment.")]
    return []


def _source_issues(source):
    issues = []
    unused = source["unused_code"]
    if unused["status"] == "attention":
        issues.append(_issue("unused_code_candidates", "low", "Unused-code candidates require review", f"Static analysis found {unused['candidate_symbols_count']} definition(s) without visible references.", "Review dynamic imports and framework registration before removing any candidate."))
    elif unused["status"] == "error":
        issues.append(_issue("unused_code_analysis_error", "medium", "Unused-code analysis failed", unused["error"], "Resolve the analysis error and repeat diagnoseProject."))
    circular = source["circular_imports"]
    if circular["status"] == "attention":
        issues.append(_issue("circular_imports", "medium", "Circular imports detected", f"Static analysis found {circular['cycles_count']} circular dependency cycle(s).", "Move shared contracts to a lower-level module or invert the dependency."))
    elif circular["status"] == "error":
        issues.append(_issue("circular_import_analysis_error", "medium", "Circular-import analysis failed", circular["error"], "Resolve the analysis error and repeat diagnoseProject."))
    return issues


def _file_issues(scan):
    issues = []
    if not scan["scan_complete"]:
        issues.append(_issue("file_scan_incomplete", "low", "File scan reached its safety limit", f"The scan stopped after {scan['maximum_file_count']} files.", "Inspect a narrower project root or use focused file commands for the remaining tree."))
    if scan["error_count"]:
        issues.append(_issue("file_scan_errors", "low", "Some file metadata could not be read", f"{scan['error_count']} file metadata read(s) failed.", "Review permissions or transient file locks and repeat the scan."))
    if scan["large_file_count"]:
        issues.append(_issue("large_files", "low", "Large files detected", f"{scan['large_file_count']} file(s) exceed {scan['large_file_threshold_formatted']}.", "Confirm each large file is intentional and appropriate for source, deployment, or project storage."))
    return issues


def build_issues(technologies, dependencies, validation, version_control, source_analysis, file_scan):
    return [
        *_project_issues(technologies, dependencies, validation),
        *_git_issues(version_control),
        *_source_issues(source_analysis),
        *_file_issues(file_scan),
    ]


def build_summary(issues, validation):
    counts = Counter(item["severity"] for item in issues)
    if counts["high"]:
        status = "critical"
    elif counts["medium"]:
        status = "attention"
    elif counts["low"]:
        status = "review"
    else:
        status = "no_issues_observed"
    configured = [name for name in ("tests", "lint", "type_checking", "build") if validation[name]["status"] == "configured_not_run"]
    commands = list(dict.fromkeys(command for name in configured for command in validation[name]["commands"]))
    return {
        "status": status,
        "issue_count": sum(item["severity"] != "info" for item in issues),
        "informational_count": counts["info"],
        "issue_counts_by_severity": {severity: counts[severity] for severity in ("high", "medium", "low", "info")},
        "issues": issues,
        "verification": {
            "level": "partial" if configured else "limited",
            "release_readiness": "not_assessed",
            "verified_areas": [
                "technology and manifest discovery", "dependency declaration inventory",
                "Git working-tree state when Git is available", "static unused-code candidates",
                "static circular-import analysis", "bounded large-file scan",
            ],
            "configured_but_not_run": configured, "suggested_commands": commands,
            "reason": "The command performs read-only inspection and never executes project-owned validation or build scripts.",
        },
    }
