#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ProjectLanguages Command - Profiles the source languages and supporting formats
that make up a project without requiring a chain of native search commands.
"""

from __future__ import annotations

import os
import re
from collections import Counter
from pathlib import Path
from typing import Any

import chardet

from qzx.core.command_base import CommandBase

try:
    import pathspec
    import pygments
    from pathspec import GitIgnoreSpec
    from pygments.lexers import (
        get_lexer_for_filename,
        guess_lexer,
    )
    from pygments.token import Comment, Text
    from pygments.util import ClassNotFound

    LANGUAGE_DEPENDENCY_ERROR = None
except ImportError as dependency_error:  # pragma: no cover - exercised via import isolation
    pathspec = None
    pygments = None
    GitIgnoreSpec = None
    get_lexer_for_filename = None
    guess_lexer = None
    Comment = None
    Text = None
    ClassNotFound = Exception
    LANGUAGE_DEPENDENCY_ERROR = dependency_error


class ProjectLanguagesCommand(CommandBase):
    """Build a trustworthy, AI-ready profile of a project's code languages."""

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
        {
            "command": "qzx projectLanguages",
            "description": "Profile languages in the current project",
        },
        {
            "command": 'qzx projectLanguages "src/"',
            "description": "Profile languages in the src/ directory",
        },
    ]

    MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024
    MAX_EXAMPLES_PER_GROUP = 5
    MAX_REPORTED_ERRORS = 20

    # These are traversal exclusions, not a language database. Language
    # detection comes from Pygments so QZX does not maintain extension lists.
    DEFAULT_EXCLUDED_DIRECTORIES = {
        ".git",
        ".hg",
        ".svn",
        ".angular",
        ".gradle",
        ".idea",
        ".mypy_cache",
        ".next",
        ".nox",
        ".nuxt",
        ".pytest_cache",
        ".ruff_cache",
        ".svelte-kit",
        ".tox",
        ".venv",
        ".vscode",
        "__pycache__",
        "bower_components",
        "build",
        "coverage",
        "dist",
        "env",
        "node_modules",
        "target",
        "venv",
        "vendor",
    }

    PROSE_ALIASES = {
        "adoc",
        "asciidoc",
        "markdown",
        "md",
        "mdown",
        "mkd",
        "rst",
        "rest",
        "text",
        "txt",
    }
    DATA_ALIASES = {
        "cfg",
        "csv",
        "ini",
        "json",
        "json5",
        "jsonld",
        "properties",
        "toml",
        "yaml",
        "yml",
    }
    MARKUP_ALIASES = {
        "haml",
        "html",
        "html5",
        "pug",
        "sgml",
        "slim",
        "svg",
        "xml",
        "xsl",
        "xslt",
    }
    STYLESHEET_ALIASES = {
        "css",
        "less",
        "sass",
        "scss",
        "stylus",
    }
    SOURCE_KINDS = {"programming", "markup", "stylesheet"}

    GENERATED_NAME_PATTERNS = (
        re.compile(r".*\.min\.(?:css|js|mjs|cjs)$", re.IGNORECASE),
        re.compile(r".*\.map$", re.IGNORECASE),
    )
    GENERATED_CONTENT_PATTERN = re.compile(
        r"(?:@generated|auto[- ]generated|automatically generated|"
        r"code generated .* do not edit|do not edit[.!]?\s*$)",
        re.IGNORECASE | re.MULTILINE,
    )

    def execute(self, scan_path="."):
        """
        Analyze a project in one pass and return language composition metrics.

        Percentages for the main composition are based on source code lines.
        If all detected source files are empty, the command falls back to bytes
        and then file counts while reporting that basis explicitly.
        """
        if LANGUAGE_DEPENDENCY_ERROR is not None:
            return {
                "success": False,
                "error_code": "missing_dependency",
                "error": str(LANGUAGE_DEPENDENCY_ERROR),
                "missing_dependencies": ["Pygments", "pathspec"],
                "remediation": (
                    "Install QZX normally or run: "
                    "python -m pip install \"Pygments>=2.20,<3\" \"pathspec>=1.1,<2\""
                ),
                "message": (
                    "Project language analysis needs the maintained Pygments "
                    "and pathspec dependencies, but they are not available."
                ),
            }

        target = Path(scan_path).expanduser().resolve()
        if not target.exists():
            return {
                "success": False,
                "error_code": "path_not_found",
                "error": f"Path '{scan_path}' does not exist.",
                "scan_path": str(target),
                "remediation": "Provide an existing project directory or source file.",
                "message": f"Cannot profile project languages because '{scan_path}' does not exist.",
            }

        if not target.is_dir() and not target.is_file():
            return {
                "success": False,
                "error_code": "unsupported_path_type",
                "error": f"Path '{scan_path}' is neither a regular file nor a directory.",
                "scan_path": str(target),
                "remediation": "Provide a regular source file or project directory.",
                "message": f"Cannot profile languages at unsupported path '{scan_path}'.",
            }

        scan_root = target if target.is_dir() else target.parent
        counters = {
            "visited_files": 0,
            "recognized_files": 0,
            "ignored_files": 0,
            "ignored_directories": 0,
            "generated_files": 0,
            "binary_files": 0,
            "unknown_files": 0,
            "oversized_files": 0,
            "symlinks_skipped": 0,
        }
        excluded_examples = {
            "generated": [],
            "binary": [],
            "oversized": [],
        }
        unknown_extensions = Counter()
        unknown_examples: list[str] = []
        scan_error_state: dict[str, Any] = {
            "total": 0,
            "items": [],
        }
        language_stats: dict[str, dict[str, Any]] = {}
        ignore_sources: list[str] = []

        if target.is_file():
            counters["visited_files"] = 1
            self._analyze_path(
                target,
                scan_root,
                counters,
                excluded_examples,
                unknown_extensions,
                unknown_examples,
                scan_error_state,
                language_stats,
            )
        else:
            ignore_scopes = self._initial_ignore_scopes(
                scan_root,
                ignore_sources,
                scan_error_state,
            )

            def record_walk_error(error):
                self._record_error(
                    scan_error_state,
                    scan_root,
                    Path(getattr(error, "filename", scan_root)),
                    error,
                )

            for root_text, directory_names, file_names in os.walk(
                scan_root,
                topdown=True,
                followlinks=False,
                onerror=record_walk_error,
            ):
                root = Path(root_text)
                if root != scan_root:
                    self._load_ignore_files(
                        root,
                        scan_root,
                        ignore_scopes,
                        ignore_sources,
                        scan_error_state,
                    )

                retained_directories = []
                for directory_name in directory_names:
                    directory_path = root / directory_name
                    if directory_path.is_symlink():
                        counters["symlinks_skipped"] += 1
                        continue
                    if directory_name.casefold() in self.DEFAULT_EXCLUDED_DIRECTORIES:
                        counters["ignored_directories"] += 1
                        continue
                    if self._is_ignored(directory_path, True, ignore_scopes):
                        counters["ignored_directories"] += 1
                        continue
                    retained_directories.append(directory_name)
                directory_names[:] = retained_directories

                for file_name in file_names:
                    file_path = root / file_name
                    counters["visited_files"] += 1
                    if file_path.is_symlink():
                        counters["symlinks_skipped"] += 1
                        continue
                    if self._is_ignored(file_path, False, ignore_scopes):
                        counters["ignored_files"] += 1
                        continue
                    self._analyze_path(
                        file_path,
                        scan_root,
                        counters,
                        excluded_examples,
                        unknown_extensions,
                        unknown_examples,
                        scan_error_state,
                        language_stats,
                    )

        languages, supporting_formats, totals, composition_basis = self._finalize_languages(
            language_stats
        )
        scan_error_count = scan_error_state["total"]
        scan_complete = scan_error_count == 0
        primary_language = languages[0]["language"] if languages else None
        languages_found = {
            entry["language"]: entry["file_count"]
            for entry in languages + supporting_formats
        }

        summary = {
            **counters,
            "analyzed_files": counters["recognized_files"],
            "source_language_count": len(languages),
            "supporting_format_count": len(supporting_formats),
            "total_language_count": len(languages) + len(supporting_formats),
            "primary_language": primary_language,
            "source_files": totals["source_files"],
            "source_bytes": totals["source_bytes"],
            "source_bytes_formatted": self._format_bytes(totals["source_bytes"]),
            "source_code_lines": totals["source_code_lines"],
            "recognized_bytes": totals["recognized_bytes"],
            "recognized_bytes_formatted": self._format_bytes(totals["recognized_bytes"]),
            "recognized_total_lines": totals["recognized_total_lines"],
            "recognized_code_lines": totals["recognized_code_lines"],
            "recognized_comment_lines": totals["recognized_comment_lines"],
            "recognized_blank_lines": totals["recognized_blank_lines"],
            "scan_error_count": scan_error_count,
        }

        exclusions = {
            "respected_ignore_files": sorted(set(ignore_sources)),
            "built_in_directory_names": sorted(self.DEFAULT_EXCLUDED_DIRECTORIES),
            "ignored_files_encountered": counters["ignored_files"],
            "ignored_directories_encountered": counters["ignored_directories"],
            "generated_files": counters["generated_files"],
            "generated_examples": excluded_examples["generated"],
            "binary_files": counters["binary_files"],
            "binary_examples": excluded_examples["binary"],
            "oversized_files": counters["oversized_files"],
            "oversized_examples": excluded_examples["oversized"],
            "max_file_size_bytes": self.MAX_FILE_SIZE_BYTES,
            "max_file_size_formatted": self._format_bytes(self.MAX_FILE_SIZE_BYTES),
            "symlinks_skipped": counters["symlinks_skipped"],
        }

        unclassified = {
            "file_count": counters["unknown_files"],
            "extensions": [
                {"extension": extension, "file_count": count}
                for extension, count in sorted(
                    unknown_extensions.items(),
                    key=lambda item: (-item[1], item[0]),
                )
            ],
            "example_files": unknown_examples,
        }

        message = self._build_message(
            target,
            languages,
            supporting_formats,
            summary,
            exclusions,
            unclassified,
            composition_basis,
            scan_complete,
            scan_error_count,
        )

        return {
            "success": True,
            "scan_path": str(target),
            "scan_kind": "directory" if target.is_dir() else "file",
            "scan_complete": scan_complete,
            "composition_basis": composition_basis,
            "summary": summary,
            "languages": languages,
            "supporting_formats": supporting_formats,
            "exclusions": exclusions,
            "unclassified": unclassified,
            "scan_errors": scan_error_state["items"],
            "scan_errors_truncated": (
                scan_error_count > len(scan_error_state["items"])
            ),
            "analysis_engine": {
                "language_detection": "Pygments",
                "language_detection_version": pygments.__version__,
                "ignore_matching": "pathspec",
                "ignore_matching_version": pathspec.__version__,
                "percentage_precision": 2,
            },
            # Compatibility fields preserve the most useful part of the former
            # Preserve the stable summary shape used by projectLanguages JSON.
            "total_files": counters["recognized_files"],
            "languages_found": languages_found,
            "message": message,
        }

    def _initial_ignore_scopes(self, scan_root, ignore_sources, scan_errors):
        scopes = []
        repository_root = self._find_repository_root(scan_root)
        scope_root = repository_root or scan_root

        if repository_root is not None:
            git_metadata = repository_root / ".git"
            if git_metadata.is_dir():
                self._load_ignore_file(
                    git_metadata / "info" / "exclude",
                    repository_root,
                    scan_root,
                    scopes,
                    ignore_sources,
                    scan_errors,
                )

        current = scope_root
        while True:
            self._load_ignore_files(
                current,
                scan_root,
                scopes,
                ignore_sources,
                scan_errors,
            )
            if current == scan_root:
                break
            try:
                relative_parts = scan_root.relative_to(current).parts
            except ValueError:
                break
            if not relative_parts:
                break
            current = current / relative_parts[0]
        return scopes

    @staticmethod
    def _find_repository_root(path):
        current = path.resolve()
        for candidate in (current, *current.parents):
            if (candidate / ".git").exists():
                return candidate
        return None

    def _load_ignore_files(
        self,
        directory,
        scan_root,
        scopes,
        ignore_sources,
        scan_errors,
    ):
        for ignore_name in (".gitignore", ".ignore"):
            self._load_ignore_file(
                directory / ignore_name,
                directory,
                scan_root,
                scopes,
                ignore_sources,
                scan_errors,
            )

    def _load_ignore_file(
        self,
        ignore_path,
        scope_path,
        scan_root,
        scopes,
        ignore_sources,
        scan_errors,
    ):
        if not ignore_path.is_file():
            return
        try:
            lines = ignore_path.read_text(encoding="utf-8-sig").splitlines()
            scopes.append((scope_path.resolve(), GitIgnoreSpec.from_lines(lines)))
            ignore_sources.append(self._relative_display(ignore_path, scan_root))
        except (OSError, UnicodeError, ValueError) as error:
            self._record_error(scan_errors, scan_root, ignore_path, error)

    @staticmethod
    def _is_ignored(path, is_directory, scopes):
        ignored = False
        for scope_path, spec in scopes:
            try:
                relative_path = path.relative_to(scope_path).as_posix()
            except ValueError:
                continue
            candidate = f"{relative_path}/" if is_directory else relative_path
            check_result = spec.check_file(candidate)
            if check_result.include is not None:
                ignored = bool(check_result.include)
        return ignored

    def _analyze_path(
        self,
        file_path,
        scan_root,
        counters,
        excluded_examples,
        unknown_extensions,
        unknown_examples,
        scan_errors,
        language_stats,
    ):
        relative_path = self._relative_display(file_path, scan_root)
        try:
            file_size = file_path.stat().st_size
            if file_size > self.MAX_FILE_SIZE_BYTES:
                counters["oversized_files"] += 1
                self._append_example(excluded_examples["oversized"], relative_path)
                return

            raw_content = file_path.read_bytes()
            if self._looks_binary(raw_content):
                counters["binary_files"] += 1
                self._append_example(excluded_examples["binary"], relative_path)
                return

            text = self._decode_text(raw_content)
            if self._is_generated(file_path.name, text):
                counters["generated_files"] += 1
                self._append_example(excluded_examples["generated"], relative_path)
                return

            lexer = self._detect_lexer(file_path.name, text)
            if lexer is None:
                counters["unknown_files"] += 1
                extension = file_path.suffix.casefold() or "(no extension)"
                unknown_extensions[extension] += 1
                self._append_example(unknown_examples, relative_path)
                return

            counts = self._count_lines(text, lexer)
            detected_variant = lexer.name
            language_name = detected_variant.split("+", 1)[0]
            aliases = sorted({alias.casefold() for alias in getattr(lexer, "aliases", [])})
            language_kind = self._language_kind(language_name, aliases)
            stats = language_stats.setdefault(
                language_name,
                {
                    "language": language_name,
                    "kind": language_kind,
                    "aliases": aliases,
                    "file_count": 0,
                    "bytes": 0,
                    "total_lines": 0,
                    "code_lines": 0,
                    "comment_lines": 0,
                    "blank_lines": 0,
                    "extensions": Counter(),
                    "detected_variants": Counter(),
                    "example_files": [],
                },
            )
            stats["file_count"] += 1
            stats["bytes"] += file_size
            stats["total_lines"] += counts["total_lines"]
            stats["code_lines"] += counts["code_lines"]
            stats["comment_lines"] += counts["comment_lines"]
            stats["blank_lines"] += counts["blank_lines"]
            stats["extensions"][file_path.suffix.casefold() or "(no extension)"] += 1
            stats["detected_variants"][detected_variant] += 1
            self._append_example(stats["example_files"], relative_path)
            counters["recognized_files"] += 1
        except (OSError, UnicodeError, ValueError) as error:
            self._record_error(scan_errors, scan_root, file_path, error)

    @staticmethod
    def _looks_binary(content):
        if not content:
            return False
        sample = content[:8192]
        if b"\x00" in sample:
            return True
        allowed_controls = {7, 8, 9, 10, 12, 13, 27}
        suspicious = sum(
            1
            for byte_value in sample
            if byte_value < 32 and byte_value not in allowed_controls
        )
        return (suspicious / len(sample)) >= 0.10

    @staticmethod
    def _decode_text(content):
        if not content:
            return ""
        try:
            return content.decode("utf-8-sig")
        except UnicodeDecodeError:
            detection = chardet.detect(content)
            encoding = detection.get("encoding")
            if encoding:
                try:
                    return content.decode(encoding)
                except (LookupError, UnicodeDecodeError):
                    pass
            return content.decode("utf-8", errors="replace")

    def _is_generated(self, file_name, text):
        if any(pattern.fullmatch(file_name) for pattern in self.GENERATED_NAME_PATTERNS):
            return True
        header = "\n".join(text.splitlines()[:20])
        return bool(self.GENERATED_CONTENT_PATTERN.search(header))

    @staticmethod
    def _detect_lexer(file_name, text):
        try:
            return get_lexer_for_filename(
                file_name,
                text,
                stripnl=False,
                ensurenl=False,
            )
        except ClassNotFound:
            if text.startswith("#!"):
                try:
                    return guess_lexer(text, stripnl=False, ensurenl=False)
                except ClassNotFound:
                    return None
            return None

    @staticmethod
    def _count_lines(text, lexer):
        physical_lines = text.splitlines()
        if not physical_lines:
            return {
                "total_lines": 0,
                "code_lines": 0,
                "comment_lines": 0,
                "blank_lines": 0,
            }

        line_states = [
            {"code": False, "comment": False}
            for _ in physical_lines
        ]
        line_index = 0
        for token_type, token_value in lexer.get_tokens(text):
            for piece in token_value.splitlines(keepends=True):
                if line_index >= len(line_states):
                    break
                content_piece = piece.rstrip("\r\n")
                if content_piece.strip():
                    if token_type in Comment:
                        line_states[line_index]["comment"] = True
                    elif not (token_type in Text and not content_piece.strip()):
                        line_states[line_index]["code"] = True
                if piece.endswith(("\n", "\r")):
                    line_index += 1

        code_lines = sum(1 for state in line_states if state["code"])
        comment_lines = sum(
            1
            for state in line_states
            if state["comment"] and not state["code"]
        )
        blank_lines = len(physical_lines) - code_lines - comment_lines
        return {
            "total_lines": len(physical_lines),
            "code_lines": code_lines,
            "comment_lines": comment_lines,
            "blank_lines": blank_lines,
        }

    def _language_kind(self, language_name, aliases):
        normalized_name = language_name.casefold()
        alias_set = set(aliases)
        if normalized_name in self.PROSE_ALIASES or alias_set & self.PROSE_ALIASES:
            return "prose"
        if normalized_name in self.DATA_ALIASES or alias_set & self.DATA_ALIASES:
            return "data"
        if normalized_name in self.STYLESHEET_ALIASES or alias_set & self.STYLESHEET_ALIASES:
            return "stylesheet"
        if normalized_name in self.MARKUP_ALIASES or alias_set & self.MARKUP_ALIASES:
            return "markup"
        return "programming"

    def _finalize_languages(self, language_stats):
        stats_values = list(language_stats.values())
        source_values = [
            stats
            for stats in stats_values
            if stats["kind"] in self.SOURCE_KINDS
        ]
        totals = {
            "source_files": sum(item["file_count"] for item in source_values),
            "source_bytes": sum(item["bytes"] for item in source_values),
            "source_code_lines": sum(item["code_lines"] for item in source_values),
            "recognized_files": sum(item["file_count"] for item in stats_values),
            "recognized_bytes": sum(item["bytes"] for item in stats_values),
            "recognized_total_lines": sum(item["total_lines"] for item in stats_values),
            "recognized_code_lines": sum(item["code_lines"] for item in stats_values),
            "recognized_comment_lines": sum(item["comment_lines"] for item in stats_values),
            "recognized_blank_lines": sum(item["blank_lines"] for item in stats_values),
        }

        if totals["source_code_lines"] > 0:
            composition_basis = "source_code_lines"
            basis_total = totals["source_code_lines"]
            basis_key = "code_lines"
        elif totals["source_bytes"] > 0:
            composition_basis = "source_bytes"
            basis_total = totals["source_bytes"]
            basis_key = "bytes"
        else:
            composition_basis = "source_file_count"
            basis_total = totals["source_files"]
            basis_key = "file_count"

        entries = []
        for stats in stats_values:
            is_source = stats["kind"] in self.SOURCE_KINDS
            composition_percentage = None
            if is_source:
                composition_percentage = self._percentage(
                    stats[basis_key],
                    basis_total,
                )
            entries.append(
                {
                    "language": stats["language"],
                    "kind": stats["kind"],
                    "aliases": stats["aliases"],
                    "composition_percentage": composition_percentage,
                    "file_count": stats["file_count"],
                    "file_percentage": self._percentage(
                        stats["file_count"],
                        totals["recognized_files"],
                    ),
                    "bytes": stats["bytes"],
                    "bytes_formatted": self._format_bytes(stats["bytes"]),
                    "byte_percentage": self._percentage(
                        stats["bytes"],
                        totals["recognized_bytes"],
                    ),
                    "total_lines": stats["total_lines"],
                    "code_lines": stats["code_lines"],
                    "code_percentage": self._percentage(
                        stats["code_lines"],
                        totals["recognized_code_lines"],
                    ),
                    "comment_lines": stats["comment_lines"],
                    "blank_lines": stats["blank_lines"],
                    "extensions": [
                        {"extension": extension, "file_count": count}
                        for extension, count in sorted(
                            stats["extensions"].items(),
                            key=lambda item: (-item[1], item[0]),
                        )
                    ],
                    "detected_variants": [
                        {"name": variant, "file_count": count}
                        for variant, count in sorted(
                            stats["detected_variants"].items(),
                            key=lambda item: (-item[1], item[0]),
                        )
                    ],
                    "example_files": stats["example_files"],
                }
            )

        languages = sorted(
            (
                entry
                for entry in entries
                if entry["kind"] in self.SOURCE_KINDS
            ),
            key=lambda entry: (
                -(entry["composition_percentage"] or 0),
                -entry["code_lines"],
                entry["language"].casefold(),
            ),
        )
        supporting_formats = sorted(
            (
                entry
                for entry in entries
                if entry["kind"] not in self.SOURCE_KINDS
            ),
            key=lambda entry: (
                -entry["code_lines"],
                -entry["file_count"],
                entry["language"].casefold(),
            ),
        )
        return languages, supporting_formats, totals, composition_basis

    def _build_message(
        self,
        target,
        languages,
        supporting_formats,
        summary,
        exclusions,
        unclassified,
        composition_basis,
        scan_complete,
        scan_error_count,
    ):
        basis_labels = {
            "source_code_lines": "source code lines",
            "source_bytes": "source bytes because the detected files contained no code lines",
            "source_file_count": "source file count because the detected files were empty",
        }
        lines = [
            "QZX Project Languages Profile",
            f"- Scanned path: {target}",
            f"- Composition basis: {basis_labels[composition_basis]}",
            (
                f"- Analyzed: {summary['analyzed_files']} recognized files, "
                f"{summary['recognized_code_lines']} code lines, "
                f"{summary['recognized_bytes_formatted']}"
            ),
            "",
        ]
        if languages:
            lines.append("Source language composition:")
            for entry in languages:
                lines.append(
                    f"  - {entry['language']}: "
                    f"{entry['composition_percentage']:.2f}% "
                    f"({self._quantity(entry['file_count'], 'file')}, "
                    f"{self._quantity(entry['code_lines'], 'code line')})"
                )
        else:
            lines.append("No source programming, markup, or stylesheet languages were detected.")

        if supporting_formats:
            lines.extend(["", "Supporting project formats:"])
            for entry in supporting_formats:
                lines.append(
                    f"  - {entry['language']} ({entry['kind']}): "
                    f"{self._quantity(entry['file_count'], 'file')}, "
                    f"{self._quantity(entry['code_lines'], 'content line')}"
                )

        lines.extend(
            [
                "",
                (
                    "Excluded or unclassified: "
                    f"{self._quantity(exclusions['ignored_directories_encountered'], 'ignored directory', 'ignored directories')}, "
                    f"{self._quantity(exclusions['ignored_files_encountered'], 'ignored file')}, "
                    f"{self._quantity(exclusions['generated_files'], 'generated file')}, "
                    f"{self._quantity(exclusions['binary_files'], 'binary file')}, "
                    f"{self._quantity(exclusions['oversized_files'], 'oversized file')}, "
                    f"{self._quantity(unclassified['file_count'], 'unknown text file')}."
                ),
                (
                    "Detection used Pygments for maintained language definitions "
                    "and pathspec for gitignore-style exclusions."
                ),
            ]
        )
        if not scan_complete:
            lines.append(
                f"The scan completed with {scan_error_count} access or read errors; "
                "inspect scan_errors in JSON for details."
            )
        return "\n".join(lines)

    @staticmethod
    def _percentage(value, total):
        if total <= 0:
            return 0.0
        return round((value / total) * 100, 2)

    @staticmethod
    def _quantity(value, singular, plural=None):
        label = singular if value == 1 else (plural or f"{singular}s")
        return f"{value} {label}"

    def _append_example(self, examples, value):
        if len(examples) < self.MAX_EXAMPLES_PER_GROUP:
            examples.append(value)

    def _record_error(self, errors, scan_root, path, error):
        errors["total"] += 1
        if len(errors["items"]) >= self.MAX_REPORTED_ERRORS:
            return
        errors["items"].append(
            {
                "path": self._relative_display(path, scan_root),
                "error_type": type(error).__name__,
                "error": str(error),
            }
        )

    @staticmethod
    def _relative_display(path, scan_root):
        try:
            relative = Path(path).resolve().relative_to(scan_root.resolve())
            return relative.as_posix() or "."
        except (OSError, ValueError):
            return os.path.relpath(path, scan_root).replace("\\", "/")
