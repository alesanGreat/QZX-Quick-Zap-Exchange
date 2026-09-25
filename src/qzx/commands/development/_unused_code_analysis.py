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


def _read_sources(paths):
    counts, contents = {}, {}
    word_pattern = re.compile(r"\b[A-Za-z0-9_]+\b")
    for path in paths:
        try:
            if os.path.getsize(path) > 1024 * 1024:
                continue
            with open(path, "r", encoding="utf-8", errors="replace") as handle:
                content = handle.read()
            contents[path] = content
            counts[path] = Counter(word_pattern.findall(content))
        except Exception:
            pass
    return counts, contents


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
    symbols = []
    for path in paths:
        if path not in contents:
            continue
        relative = os.path.relpath(path, root).replace(os.path.sep, "/")
        extractors[os.path.splitext(path)[1].lower()](contents[path], path, relative, symbols)
    return symbols


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


def _message(file_count, symbols, candidates):
    message = (
        "Unused Code Candidate Report:\n"
        f"- Total files scanned: {file_count}\n"
        f"- Total symbols analyzed: {len(symbols)}\n"
        f"- Candidates requiring review: {len(candidates)}\n"
    )
    if not candidates:
        return message + "\nNo unused-code candidates were detected.\n"
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
    token_counts, contents = _read_sources(paths)
    symbols = _extract_symbols(command, paths, root, contents)
    candidates = _candidates(symbols, token_counts)
    return {
        "success": True, "scan_path": root,
        "analyzed_symbols_count": len(symbols),
        "candidate_symbols_count": len(candidates),
        "candidate_symbols": candidates,
        "message": _message(len(paths), symbols, candidates),
    }
