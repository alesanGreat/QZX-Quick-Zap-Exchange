"""Command orchestration for ``analyzeComplexity``."""

import os

from qzx.core.recursive_findfiles_utils import find_files, parse_recursive_parameter


def _failure(path, detail_level):
    if not os.path.exists(path):
        return {
            "success": False,
            "error_code": "path_not_found",
            "error": f"Path '{path}' does not exist.",
            "message": "Check the analysis path and try again.",
        }
    normalized = str(detail_level or "").strip().lower()
    if normalized not in {"detailed", "summary"}:
        return {
            "success": False,
            "error_code": "invalid_detail_level",
            "error": "detail_level must be 'detailed' or 'summary'.",
            "message": "Choose a detailed per-file report or a summary report.",
            "details": {"path": os.path.abspath(path), "detail_level": detail_level},
        }
    return None


def _collect(command, path, recursive):
    if os.path.isfile(path):
        analysis = command._analyze_file(path)
        return [analysis] if analysis else [], 1
    results = []
    total = 0
    for found_path in find_files(
        file_path_pattern=path,
        recursive=parse_recursive_parameter(recursive),
        file_type="f",
    ):
        if os.path.splitext(found_path)[1].lower() not in command.SUPPORTED_EXTENSIONS:
            continue
        total += 1
        analysis = command._analyze_file(found_path)
        if analysis:
            results.append(analysis)
    return results, total


def _partition_analyses(results):
    analyses = [item for item in results if "error" not in item]
    issues = [item for item in results if "error" in item]
    return analyses, issues


def _incomplete_result(command, analyses, issues, total, level, details):
    details.update(
        failed_files=len(issues),
        scan_issues=issues,
    )
    result = {
        "success": False,
        "analysis_complete": False,
        "error_code": "complexity_analysis_incomplete",
        "error": "One or more supported source files could not be analyzed completely.",
        "message": (
            f"Analyzed {len(analyses)} of {total} supported source file(s); "
            f"{len(issues)} file(s) could not be analyzed."
        ),
        "details": details,
    }
    if analyses:
        result["report"] = command._format_results(
            analyses, total, len(analyses), level
        )
    return result


def execute_complexity(command, file_path, recursive=False, detail_level="detailed"):
    failure = _failure(file_path, detail_level)
    if failure:
        return failure
    level = str(detail_level or "").strip().lower()
    results, total = _collect(command, file_path, recursive)
    analyses, issues = _partition_analyses(results)
    analyzed = len(analyses)
    details = {
        "path": os.path.abspath(file_path),
        "files_seen": total,
        "files_analyzed": analyzed,
        "detail_level": level,
        "analyses": analyses,
    }
    if issues:
        return _incomplete_result(
            command, analyses, issues, total, level, details
        )
    if not analyses:
        details["supported_extensions"] = sorted(command.SUPPORTED_EXTENSIONS)
        return {
            "success": True,
            "analysis_complete": True,
            "message": f"No supported source files were found in '{file_path}'.",
            "details": details,
        }
    return {
        "success": True,
        "analysis_complete": True,
        "message": f"Analyzed {analyzed} of {total} supported source file(s).",
        "report": command._format_results(analyses, total, analyzed, level),
        "details": details,
    }
