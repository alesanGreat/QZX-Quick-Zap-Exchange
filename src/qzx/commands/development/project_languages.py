#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Profile the source languages and supporting formats in a project."""

from qzx.core.command_base import CommandBase

from ._project_language_command import execute_project_languages
from ._project_language_constants import (
    DATA_ALIASES,
    DEFAULT_EXCLUDED_DIRECTORIES,
    GENERATED_CONTENT_PATTERN,
    GENERATED_NAME_PATTERNS,
    MARKUP_ALIASES,
    PROSE_ALIASES,
    SOURCE_KINDS,
    STYLESHEET_ALIASES,
)
from ._project_language_results import (
    build_message,
    finalize_languages,
    make_exclusions,
    make_summary,
    make_unclassified,
    percentage,
    quantity,
)
from ._project_language_scan import (
    LANGUAGE_DEPENDENCY_ERROR,
    analyze_path,
    append_example,
    count_lines,
    decode_text,
    detect_lexer,
    find_repository_root,
    initial_ignore_scopes,
    is_generated,
    is_ignored,
    language_kind,
    load_ignore_file,
    load_ignore_files,
    looks_binary,
    pathspec,
    portable_dependencies,
    record_error,
    relative_display,
)


class ProjectLanguagesCommand(CommandBase):
    """Build a trustworthy, AI-ready profile of project languages."""

    name = "projectLanguages"
    description = (
        "Profiles a project's source languages and supporting formats with "
        "line, file, and byte percentages"
    )
    category = "development"
    parameters = [
        {
            "name": "scan_path",
            "description": "Project directory or source file to analyze (defaults to current directory)",
            "required": False,
            "default": ".",
            "type": "str",
        }
    ]
    examples = [
        {"command": "qzx projectLanguages", "description": "Profile languages in the current project"},
        {"command": 'qzx projectLanguages "src/"', "description": "Profile languages in the src/ directory"},
    ]

    MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024
    MAX_EXAMPLES_PER_GROUP = 5
    MAX_REPORTED_ERRORS = 20
    DEFAULT_EXCLUDED_DIRECTORIES = DEFAULT_EXCLUDED_DIRECTORIES
    PROSE_ALIASES = PROSE_ALIASES
    DATA_ALIASES = DATA_ALIASES
    MARKUP_ALIASES = MARKUP_ALIASES
    STYLESHEET_ALIASES = STYLESHEET_ALIASES
    SOURCE_KINDS = SOURCE_KINDS
    GENERATED_NAME_PATTERNS = GENERATED_NAME_PATTERNS
    GENERATED_CONTENT_PATTERN = GENERATED_CONTENT_PATTERN

    _initial_ignore_scopes = initial_ignore_scopes
    _find_repository_root = staticmethod(find_repository_root)
    _load_ignore_files = load_ignore_files
    _load_ignore_file = load_ignore_file
    _is_ignored = staticmethod(is_ignored)
    _analyze_path = analyze_path
    _looks_binary = staticmethod(looks_binary)
    _decode_text = staticmethod(decode_text)
    _is_generated = is_generated
    _detect_lexer = staticmethod(detect_lexer)
    _count_lines = staticmethod(count_lines)
    _language_kind = language_kind
    _finalize_languages = finalize_languages
    _build_message = build_message
    _percentage = staticmethod(percentage)
    _quantity = staticmethod(quantity)
    _append_example = append_example
    _record_error = record_error
    _relative_display = staticmethod(relative_display)
    _make_summary = make_summary
    _make_exclusions = make_exclusions
    _make_unclassified = staticmethod(make_unclassified)

    def execute(self, scan_path="."):
        return execute_project_languages(
            self,
            scan_path,
            LANGUAGE_DEPENDENCY_ERROR,
            None,
            pathspec,
            portable_dependency_loader=portable_dependencies,
        )
