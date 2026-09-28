"""Static token/reference workflow for ``findUnusedCode``."""

import os
import re
from collections import Counter

from qzx.core.recursive_findfiles_utils import (
    SOURCE_ANALYSIS_EXCLUDED_DIRECTORIES,
    find_files,
)


def _source_files(command, path):
    def supported(candidate):
        return os.path.splitext(candidate)[1].lower() in command.SUPPORTED_EXTENSIONS
    if os.path.isfile(path):
        return [path] if supported(path) else []
    if not os.path.isdir(path):
        return []
    return [
        candidate
        for candidate in find_files(
            path, recursive=True,
            exclude_dirs=SOURCE_ANALYSIS_EXCLUDED_DIRECTORIES,
            file_type="f",
        )
        if supported(candidate)
    ]


_MAX_SYMBOL_CONTENT_BYTES = 1024 * 1024
_WORD_PATTERN = re.compile(r"\b[A-Za-z0-9_]+\b")


def _scan_issue(path, root, reason, **details):
    issue = {
        "file": os.path.relpath(path, root).replace(os.path.sep, "/"),
        "reason": reason,
    }
    issue.update(details)
    return issue


def _read_sources(paths, root):
    counts, contents, issues = {}, {}, []
    for path in paths:
        try:
            size_bytes = os.path.getsize(path)
            with open(path, "r", encoding="utf-8", errors="replace") as handle:
                if size_bytes > _MAX_SYMBOL_CONTENT_BYTES:
                    counts[path] = Counter()
                    for line in handle:
                        counts[path].update(_WORD_PATTERN.findall(line))
                    issues.append(_scan_issue(
                        path, root, "too_large_for_symbol_extraction",
                        size_bytes=size_bytes, limit_bytes=_MAX_SYMBOL_CONTENT_BYTES,
                    ))
                    continue
                content = handle.read()
            contents[path] = content
            counts[path] = Counter(_WORD_PATTERN.findall(content))
        except OSError as exc:
            issues.append(_scan_issue(
                path, root, "source_read_failed",
                error_type=type(exc).__name__, message=str(exc),
            ))
    return counts, contents, issues


def _extract_symbols(command, paths, root, contents):
    extractors = {
        ".py": command._extract_python_symbols,
        ".js": command._extract_js_ts_symbols, ".jsx": command._extract_js_ts_symbols,
        ".ts": command._extract_js_ts_symbols, ".tsx": command._extract_js_ts_symbols,
        ".php": command._extract_php_symbols, ".rs": command._extract_rust_symbols,
        ".cpp": command._extract_cpp_symbols, ".hpp": command._extract_cpp_symbols,
        ".cc": command._extract_cpp_symbols, ".cxx": command._extract_cpp_symbols,
        ".h": command._extract_cpp_symbols, ".go": command._extract_go_symbols,
        ".java": command._extract_java_symbols, ".kt": command._extract_kotlin_symbols,
        ".cs": command._extract_csharp_symbols,
    }
    symbols, issues = [], []
    for path in paths:
        if path not in contents:
            continue
        relative = os.path.relpath(path, root).replace(os.path.sep, "/")
        try:
            extractors[os.path.splitext(path)[1].lower()](
                contents[path], path, relative, symbols
            )
        except (SyntaxError, ValueError) as exc:
            issues.append(_scan_issue(
                path, root, "symbol_extraction_failed",
                error_type=type(exc).__name__, message=str(exc),
            ))
    return symbols, issues


def _candidates(symbols, token_counts):
    candidates = []
    for symbol in symbols:
        referenced = any(
            counts[symbol["name"]] > (1 if path == symbol["file_abs"] else 0)
            for path, counts in token_counts.items()
        )
        if not referenced:
            candidates.append({
                "name": symbol["name"], "type": symbol["type"],
                "file": symbol["file_rel"], "line_number": symbol["line_number"],
                "reason": "No statically visible references were found in the analyzed source files.",
            })
    return candidates


def _message(file_count, symbols, candidates, issues):
    message = (
        "Unused Code Candidate Report:\n"
        f"- Total files scanned: {file_count}\n"
        f"- Files with incomplete symbol analysis: {len(issues)}\n"
        f"- Total symbols analyzed: {len(symbols)}\n"
        f"- Candidates requiring review: {len(candidates)}\n"
    )
    if issues:
        message += (
            "\n[INCOMPLETE] Some source files could not be fully analyzed; "
            "candidate findings below are partial.\n"
        )
        for issue in issues[:10]:
            message += f"  - {issue['file']}: {issue['reason']}\n"
    if not candidates:
        suffix = " in successfully analyzed files" if issues else ""
        return message + f"\nNo unused-code candidates were detected{suffix}.\n"
    message += "\nPotentially unused definitions (review dynamic or reflective uses before removal):\n"
    for index, symbol in enumerate(candidates[:15], 1):
        message += f"  {index}. [{symbol['type'].upper()}] '{symbol['name']}' at {symbol['file']}:{symbol['line_number']}\n"
    if len(candidates) > 15:
        message += f"  ... and {len(candidates) - 15} more candidates.\n"
    return message


def execute_unused_code_analysis(command, scan_path="."):
    """Find statically unreferenced definitions without claiming deletion safety."""
    root = os.path.abspath(scan_path)
    if not os.path.exists(root):
        message = f"Path '{scan_path}' does not exist."
        return {"success": False, "error": message, "message": message}
    paths = _source_files(command, root)
    if not paths:
        return {"success": True, "candidate_symbols_count": 0, "candidate_symbols": [], "message": "No supported source files found to analyze."}
    token_counts, contents, read_issues = _read_sources(paths, root)
    symbols, extraction_issues = _extract_symbols(command, paths, root, contents)
    issues = read_issues + extraction_issues
    candidates = _candidates(symbols, token_counts)
    result = {
        "success": not issues, "scan_path": root,
        "analysis_complete": not issues,
        "files_scanned": len(paths),
        "analyzed_symbols_count": len(symbols),
        "candidate_symbols_count": len(candidates),
        "candidate_symbols": candidates,
        "message": _message(len(paths), symbols, candidates, issues),
    }
    if issues:
        result.update({
            "error": "Unused-code analysis was incomplete.",
            "error_code": "source_scan_incomplete",
            "scan_issues": issues,
        })
    return result
