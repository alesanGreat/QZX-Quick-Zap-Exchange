"""Request normalization and traversal orchestration for findText."""

from __future__ import annotations

from dataclasses import dataclass
import os
import re
import sys

import colorama

from qzx.core.recursive_findfiles_utils import find_files, parse_recursive_parameter

from ._text_search_file import search_text_file
from ._text_search_targets import split_text_search_targets


TRUE_TEXT = frozenset({"true", "yes", "y", "1"})


class SearchRequestError(ValueError):
    """Invalid findText request value."""


@dataclass(frozen=True)
class TextSearchRequest:
    pattern: str
    target: str
    recursive: object
    regex: bool
    case_sensitive: bool
    file_pattern: str
    context_lines: int
    invert_match: bool
    count_only: bool
    max_matches: int
    colored: bool
    search_pattern: object
    target_paths: tuple[str, ...]
    recursion_message: str


@dataclass
class TextSearchState:
    results: list
    total_matches: int = 0
    files_with_matches: int = 0
    files_searched: int = 0


def _boolean(value):
    if isinstance(value, str):
        return value.lower() in TRUE_TEXT
    return value


def _integer(value, name):
    if not isinstance(value, str):
        return value
    try:
        return int(value)
    except ValueError as exc:
        raise SearchRequestError(
            f"Invalid {name} value: {value}. Must be a number."
        ) from exc


def _console_colors_supported(colored):
    if not colored or sys.platform != "win32" or sys.stdout.encoding == "utf-8":
        return colored
    try:
        sample = f"{colorama.Fore.RED}Test{colorama.Style.RESET_ALL}"
        sample.encode(sys.stdout.encoding or "utf-8")
        return True
    except (LookupError, UnicodeEncodeError):
        return False


def _compiled_pattern(pattern, regex_enabled, case_sensitive):
    if not regex_enabled:
        return pattern
    try:
        flags = 0 if case_sensitive else re.IGNORECASE
        return re.compile(pattern, flags)
    except re.error as exc:
        raise SearchRequestError(f"Invalid regular expression: {str(exc)}") from exc


def _recursion_message(recursive):
    if recursive is True or recursive is None:
        return " (including all subdirectories)"
    if isinstance(recursive, int) and recursive > 0:
        plural = "s" if recursive > 1 else ""
        return f" (including subdirectories up to {recursive} level{plural})"
    return ""


def build_text_search_request(pattern, target, recursive, regex_enabled,
                              case_sensitive, file_pattern, context_lines,
                              invert_match, count_only, max_matches, colored):
    recursive = parse_recursive_parameter(recursive)
    regex_enabled = _boolean(regex_enabled)
    case_sensitive = _boolean(case_sensitive)
    invert_match = _boolean(invert_match)
    count_only = _boolean(count_only)
    colored = _console_colors_supported(_boolean(colored))
    context_lines = _integer(context_lines, "context_lines")
    max_matches = _integer(max_matches, "max_matches")
    return TextSearchRequest(
        pattern=pattern,
        target=target,
        recursive=recursive,
        regex=regex_enabled,
        case_sensitive=case_sensitive,
        file_pattern=file_pattern,
        context_lines=context_lines,
        invert_match=invert_match,
        count_only=count_only,
        max_matches=max_matches,
        colored=colored,
        search_pattern=_compiled_pattern(pattern, regex_enabled, case_sensitive),
        target_paths=tuple(split_text_search_targets(target)),
        recursion_message=_recursion_message(recursive),
    )


def _limit_reached(request, state):
    return request.max_matches > 0 and state.total_matches >= request.max_matches


def _record_file(request, state, file_path):
    if _limit_reached(request, state):
        return
    state.files_searched += 1
    result = search_text_file(
        file_path,
        request.search_pattern,
        request.regex,
        request.case_sensitive,
        request.context_lines,
        request.invert_match,
        request.count_only,
        request.colored,
    )
    if result:
        state.results.append(result)
        state.total_matches += result["matches"]
        state.files_with_matches += 1


def _search_directory(request, state, path):
    search_path = os.path.join(path, request.file_pattern)

    def on_file_found(file_path):
        _record_file(request, state, file_path)

    for _ in find_files(
        file_path_pattern=search_path,
        recursive=request.recursive,
        file_type="f",
        on_file_found=on_file_found,
    ):
        if _limit_reached(request, state):
            break


def search_text_targets(request):
    state = TextSearchState(results=[])
    for path in request.target_paths:
        if os.path.isfile(path):
            _record_file(request, state, path)
        elif os.path.isdir(path):
            _search_directory(request, state, path)
        if _limit_reached(request, state):
            break
    return state


def _result_message(request, state):
    if state.files_with_matches == 0:
        suffix = "s" if state.files_searched != 1 else ""
        return (
            f"No matches found for '{request.pattern}' in "
            f"{state.files_searched} file{suffix}{request.recursion_message}"
        )
    match_suffix = "es" if state.total_matches != 1 else ""
    file_suffix = "s" if state.files_with_matches != 1 else ""
    message = (
        f"Found {state.total_matches} match{match_suffix} in "
        f"{state.files_with_matches} file{file_suffix}{request.recursion_message}"
    )
    if _limit_reached(request, state):
        message += f" (stopped after {request.max_matches} matches)"
    return message


def build_text_search_result(request, state):
    return {
        "success": True,
        "pattern": request.pattern,
        "target": request.target,
        "regex": request.regex,
        "case_sensitive": request.case_sensitive,
        "file_pattern": request.file_pattern,
        "recursive": (
            "unlimited"
            if request.recursive is None
            else "none"
            if request.recursive == 0
            else request.recursive
        ),
        "context_lines": request.context_lines,
        "invert_match": request.invert_match,
        "files_searched": state.files_searched,
        "files_with_matches": state.files_with_matches,
        "total_matches": state.total_matches,
        "results": state.results,
        "message": _result_message(request, state),
    }


def execute_text_search(pattern, target, recursive=None, regex_enabled=False,
                        case_sensitive=True, file_pattern="*", context_lines=0,
                        invert_match=False, count_only=False, max_matches=0,
                        colored=True):
    """Normalize, search and render a findText request."""
    try:
        request = build_text_search_request(
            pattern,
            target,
            recursive,
            regex_enabled,
            case_sensitive,
            file_pattern,
            context_lines,
            invert_match,
            count_only,
            max_matches,
            colored,
        )
        return build_text_search_result(request, search_text_targets(request))
    except Exception as exc:
        return {"success": False, "error": str(exc)}
