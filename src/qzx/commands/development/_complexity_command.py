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
        return [analysis] if analysis else [], 1, int(bool(analysis))
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
    return results, total, len(results)


def execute_complexity(command, file_path, recursive=False, detail_level="detailed"):
    failure = _failure(file_path, detail_level)
    if failure:
        return failure
    level = str(detail_level or "").strip().lower()
    results, total, analyzed = _collect(command, file_path, recursive)
    if not results:
        return {
            "success": True,
            "message": f"No supported source files were found in '{file_path}'.",
            "details": {
                "path": os.path.abspath(file_path),
                "files_seen": total,
                "files_analyzed": 0,
                "supported_extensions": sorted(command.SUPPORTED_EXTENSIONS),
            },
        }
    report = command._format_results(results, total, analyzed, level)
    return {
        "success": True,
        "message": f"Analyzed {analyzed} of {total} supported source file(s).",
        "report": report,
        "details": {
            "path": os.path.abspath(file_path),
            "files_seen": total,
            "files_analyzed": analyzed,
            "detail_level": level,
            "analyses": results,
        },
    }
