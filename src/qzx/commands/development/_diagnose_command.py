"""Orchestration for read-only project diagnosis."""

import json
import tomllib
from pathlib import Path

from qzx.core.project_validation import inspect_validation_workflows


def _project_root(path):
    root = Path(path).expanduser().resolve()
    if not root.exists():
        return None, {"success": False, "error": f"Path '{path}' does not exist.", "message": f"Cannot diagnose the project because '{path}' does not exist."}
    if not root.is_dir():
        return None, {"success": False, "error": f"Path '{path}' is not a directory.", "message": f"Cannot diagnose '{path}': diagnoseProject requires a directory."}
    return root, None


def _documents(command, root):
    return (
        command._read_document(root / "pyproject.toml", tomllib.loads, (tomllib.TOMLDecodeError,)),
        command._read_document(root / "package.json", json.loads, (json.JSONDecodeError,)),
        command._read_document(root / "composer.json", json.loads, (json.JSONDecodeError,)),
    )


def _details(command, root):
    root_names = {entry.name for entry in root.iterdir()}
    pyproject, package_json, composer_json = _documents(command, root)
    technologies = command._detect_technologies(root, root_names)
    dependencies = command._inspect_dependencies(root, pyproject, package_json, composer_json)
    validation = inspect_validation_workflows(root, root_names, technologies, pyproject, package_json, composer_json)
    version_control = command._inspect_git(root)
    source_analysis = command._inspect_source(root)
    file_scan = command._scan_large_files(root)
    issues = command._build_issues(technologies, dependencies, validation, version_control, source_analysis, file_scan)
    summary = command._build_summary(issues, validation)
    return {
        "path": str(root), "technologies": technologies,
        "dependencies": dependencies, "environment": command._inspect_environment(root_names),
        "validation": validation, "version_control": version_control,
        "source_analysis": source_analysis, "file_scan": file_scan, "summary": summary,
    }


def _message(summary):
    issue_count = summary["issue_count"]
    if issue_count:
        message = f"Project diagnosis completed with {issue_count} observed issue{'s' if issue_count != 1 else ''}."
    else:
        message = "Project diagnosis completed with no observed issues."
    pending = len(summary["verification"]["configured_but_not_run"])
    if pending:
        return message + f" {pending} configured validation workflow{'s were' if pending != 1 else ' was'} discovered but not executed; run the suggested commands before treating the project as release-ready."
    return message + " No executable validation workflow was discovered, so release readiness was not assessed."


def execute_diagnosis(command, path="."):
    root, failure = _project_root(path)
    if failure:
        return failure
    details = _details(command, root)
    result = {"success": True, "message": _message(details["summary"]), "details": details}
    result["report"] = command._render_report(details)
    return result
