"""Multi-file workflow for getHumanLanguageStats."""

from __future__ import annotations

import sys

from qzx.core.recursive_findfiles_utils import (
    find_files,
    parse_recursive_parameter,
)


def execute_human_language_stats(
    command,
    file_path,
    ignore_comments=False,
    min_word_length=4,
    languages=None,
    recursive=False,
    show_files_match=False,
):
    """Discover files, analyze them, and assemble the stable public result."""
    warnings = _base_warnings(command)
    options = _normalized_options(
        ignore_comments,
        languages,
        recursive,
        show_files_match,
    )
    selected_words = _selected_function_words(
        command,
        options["languages"],
        warnings,
    )
    files_found = _matching_files(file_path, options["recursive"])
    if not files_found:
        result = {
            "success": False,
            "status": "error",
            "error": f"No files found matching '{file_path}'",
            "message": f"No files found matching '{file_path}'",
        }
        if warnings:
            result["warnings"] = warnings
        return result

    file_stats = _analyze_files(
        command,
        files_found,
        options["ignore_comments"],
        min_word_length,
        selected_words,
    )
    return _analysis_result(
        command,
        files_found,
        file_stats,
        options["show_files_match"],
        warnings,
    )


def _base_warnings(command):
    warnings = list(command.dictionary_warnings)
    if not command.function_words:
        fallback = (
            "No human-language word dictionaries are available; "
            "character-based fallback analysis is less accurate."
        )
        if fallback not in warnings:
            warnings.append(fallback)
    return warnings


def _normalized_options(
    ignore_comments,
    languages,
    recursive,
    show_files_match,
):
    args = sys.argv
    if isinstance(ignore_comments, str):
        ignore_comments = ignore_comments.lower() in {"-i", "--ignore-comments"}

    recursive_flags = {"-r", "-R", "--recursive"}
    if isinstance(recursive, str):
        recursive = parse_recursive_parameter(recursive)
    elif any(flag in args for flag in recursive_flags):
        recursive = True

    show_flags = {"--show_files_match", "-show_files_match"}
    if isinstance(show_files_match, str):
        show_files_match = show_files_match.lower() in show_flags
    elif any(flag in args for flag in show_flags):
        show_files_match = True

    language_list = None
    if languages:
        language_list = [
            language.strip().lower()
            for language in languages.split(",")
        ]
    return {
        "ignore_comments": ignore_comments,
        "languages": language_list,
        "recursive": recursive,
        "show_files_match": show_files_match,
    }


def _selected_function_words(command, language_list, warnings):
    selected = {
        language: words
        for language, words in command.function_words.items()
        if language_list is None or language in language_list
    }
    if not selected:
        warning = (
            "No selected human-language word dictionaries are available; "
            "results may be less accurate."
        )
        if warning not in warnings:
            warnings.append(warning)
    return selected


def _matching_files(file_path, recursive):
    files = []

    def on_file_found(found_path):
        files.append(found_path)

    for _ in find_files(
        file_path_pattern=file_path,
        recursive=recursive,
        file_type="f",
        on_file_found=on_file_found,
    ):
        pass
    return files


def _analyze_files(
    command,
    files_found,
    ignore_comments,
    min_word_length,
    selected_words,
):
    file_stats = {}
    for found_path in files_found:
        try:
            file_stats[found_path] = command._analyze_file(
                found_path,
                ignore_comments,
                min_word_length,
                selected_words,
            )
        except Exception as exc:
            file_stats[found_path] = {"error": str(exc)}
    return file_stats


def _analysis_result(
    command,
    files_found,
    file_stats,
    show_files_match,
    warnings,
):
    failed_files = [
        path for path, stats in file_stats.items() if "error" in stats
    ]
    processed = len(files_found)
    analyzed = processed - len(failed_files)
    result = {
        "success": not failed_files,
        "status": "success" if not failed_files else "error",
        "message": (
            f"Analyzed human-language content in {analyzed} of "
            f"{processed} file(s)."
        ),
        "files_processed": processed,
        "files_analyzed": analyzed,
        "files_failed": len(failed_files),
        "files_found": processed,
        "file_stats": file_stats,
        "aggregated_stats": command._aggregate_stats(file_stats),
    }
    if show_files_match:
        result["matched_files"] = files_found
    if failed_files:
        result["error_code"] = "partial_analysis_failure"
        result["error"] = (
            f"Analysis failed for {len(failed_files)} of "
            f"{processed} matched file(s)."
        )
    if warnings:
        result["warnings"] = warnings
    return result
