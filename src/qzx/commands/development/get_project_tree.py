#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Generate one bounded, symlink-safe project tree from a single scan."""

from __future__ import annotations

import heapq
import os
from dataclasses import dataclass, field
from pathlib import Path

from qzx.core.command_base import CommandBase


_DEFAULT_EXCLUDES = (
    ".git",
    ".idea",
    ".next",
    ".nuxt",
    ".venv",
    ".vscode",
    "__pycache__",
    "artifacts",
    "build",
    "dist",
    "env",
    "node_modules",
)
_DEFAULT_EXCLUDES_TEXT = ",".join(_DEFAULT_EXCLUDES)


@dataclass
class _TreeScanState:
    """Mutable counters and bounded evidence for one tree traversal."""

    root: Path
    max_entries: int
    entry_count: int = 0
    directory_count: int = 0
    file_count: int = 0
    symlink_count: int = 0
    other_count: int = 0
    unavailable_count: int = 0
    excluded_directory_count: int = 0
    skipped_file_count: int = 0
    scan_error_count: int = 0
    scan_error_samples: list[dict[str, str]] = field(default_factory=list)
    entry_limit_reached: bool = False

    @property
    def remaining_entries(self):
        return max(0, self.max_entries - self.entry_count)

    def record_error(self, path, error):
        self.scan_error_count += 1
        if len(self.scan_error_samples) < 20:
            self.scan_error_samples.append(
                {
                    "path": str(path),
                    "error_type": type(error).__name__,
                    "error": str(error),
                }
            )

    def record_entry(self, entry_type):
        self.entry_count += 1
        if entry_type == "directory":
            self.directory_count += 1
        elif entry_type == "file":
            self.file_count += 1
        elif entry_type == "symlink":
            self.symlink_count += 1
        elif entry_type == "unavailable":
            self.unavailable_count += 1
        else:
            self.other_count += 1


class GetProjectTreeCommand(CommandBase):
    """Build a deterministic project tree without following descendant links."""

    name = "getProjectTree"
    description = (
        "Generates one bounded ASCII and JSON directory tree without following "
        "descendant symbolic links"
    )
    category = "development"

    MAX_DEPTH = 64
    MAX_ENTRIES = 100_000

    parameters = [
        {
            "name": "dir_path",
            "description": "Directory to visualize (defaults to the current directory)",
            "required": False,
            "default": ".",
            "type": "str",
        },
        {
            "name": "max_depth",
            "description": "Maximum descendant depth from 0 through 64",
            "required": False,
            "default": 2,
            "type": "int",
        },
        {
            "name": "exclude_dirs",
            "description": (
                "Comma-separated directory names to exclude; matching is "
                "case-insensitive"
            ),
            "required": False,
            "default": _DEFAULT_EXCLUDES_TEXT,
            "type": "str",
        },
        {
            "name": "include_files",
            "description": (
                "List regular files as well as directories; links are always "
                "listed but never followed"
            ),
            "required": False,
            "default": True,
            "type": "bool",
        },
        {
            "name": "max_entries",
            "description": (
                "Maximum retained descendants from 1 through 100000 "
                "(defaults to 10000)"
            ),
            "required": False,
            "default": 10_000,
            "type": "int",
        },
    ]

    examples = [
        {
            "command": "qzx getProjectTree",
            "description": "Show the current project through two descendant levels",
        },
        {
            "command": "qzx getProjectTree src 3",
            "description": "Show the src tree through three descendant levels",
        },
        {
            "command": (
                "qzx getProjectTree . 2 .git,node_modules false "
                "--max_entries 500"
            ),
            "description": (
                "Show at most 500 directory/link entries while excluding two names"
            ),
        },
    ]

    def __init__(self, *, scandir=None, readlink=None):
        super().__init__()
        self._scandir = scandir or os.scandir
        self._readlink = readlink or os.readlink

    def execute(
        self,
        dir_path=".",
        max_depth=2,
        exclude_dirs=None,
        include_files=True,
        max_entries=10_000,
    ):
        """Return one bounded tree model and render it without rescanning."""

        normalized_path, path_error = self._normalize_directory(dir_path)
        if path_error is not None:
            return path_error

        depth, depth_error = self._bounded_integer(
            max_depth,
            field="max_depth",
            minimum=0,
            maximum=self.MAX_DEPTH,
        )
        if depth_error is not None:
            return depth_error

        entry_limit, entry_limit_error = self._bounded_integer(
            max_entries,
            field="max_entries",
            minimum=1,
            maximum=self.MAX_ENTRIES,
        )
        if entry_limit_error is not None:
            return entry_limit_error

        show_files = self._normalize_boolean(include_files)
        if show_files is None:
            return {
                "success": False,
                "error_code": "invalid_include_files",
                "error": (
                    "include_files must be a boolean or an unambiguous "
                    "true/false token."
                ),
                "message": "Choose whether regular files appear in the project tree.",
            }

        excludes, exclude_error = self._normalize_excludes(exclude_dirs)
        if exclude_error is not None:
            return exclude_error

        state = _TreeScanState(root=normalized_path, max_entries=entry_limit)
        root_node = {
            "name": normalized_path.name or str(normalized_path),
            "type": "directory",
            "children": [],
        }
        self._populate_directory(
            root_node,
            normalized_path,
            current_depth=0,
            max_depth=depth,
            excludes=excludes,
            include_files=show_files,
            state=state,
        )

        details = {
            "entry_count": state.entry_count,
            "tree_node_count_including_root": state.entry_count + 1,
            "directory_count": state.directory_count,
            "file_count": state.file_count,
            "symlink_count": state.symlink_count,
            "other_count": state.other_count,
            "unavailable_count": state.unavailable_count,
            "excluded_directory_count": state.excluded_directory_count,
            "skipped_file_count": state.skipped_file_count,
            "scan_complete": (
                state.scan_error_count == 0 and not state.entry_limit_reached
            ),
            "scan_error_count": state.scan_error_count,
            "entry_limit_reached": state.entry_limit_reached,
            "symbolic_links_followed": False,
            "symlink_policy": "listed_not_followed",
            "sorting": "directories_files_links_other_then_casefolded_name",
        }
        if state.scan_error_samples:
            details["scan_error_samples"] = state.scan_error_samples

        tree_text = self._render_tree(root_node)
        warnings = []
        if state.entry_limit_reached:
            warnings.append(
                "The retained-entry limit was reached; the tree is intentionally partial."
            )
        if state.scan_error_count:
            warnings.append(
                "{} filesystem entr{} could not be read; the tree contains bounded "
                "error evidence.".format(
                    state.scan_error_count,
                    "y" if state.scan_error_count == 1 else "ies",
                )
            )

        if root_node.get("scan_error"):
            root_error = root_node["scan_error"]
            return {
                "success": False,
                "error_code": "directory_scan_failed",
                "error": (
                    f"{root_error['error_type']}: {root_error['error']}"
                ),
                "message": (
                    f"QZX could not read the root directory '{normalized_path}'."
                ),
                "dir_path": str(normalized_path),
                "tree_text": tree_text,
                "tree_structure": root_node,
                "details": details,
            }

        message = (
            f"Generated a project tree for '{normalized_path}' with "
            f"{state.entry_count} retained descendant"
            f"{'s' if state.entry_count != 1 else ''}; descendant links were "
            "listed but not followed."
        )
        result = {
            "success": True,
            "message": message,
            "dir_path": str(normalized_path),
            "max_depth": depth,
            "max_entries": entry_limit,
            "exclude_dirs": sorted(excludes),
            "include_files": show_files,
            "tree_text": tree_text,
            "tree_structure": root_node,
            "details": details,
        }
        if warnings:
            result["warnings"] = warnings
        return result

    @staticmethod
    def _normalize_directory(dir_path):
        try:
            raw_path = os.fspath(dir_path)
        except TypeError:
            return None, {
                "success": False,
                "error_code": "invalid_directory_path",
                "error": "dir_path must be text or a filesystem path object.",
                "message": "Provide a directory path for the project tree.",
            }
        if not isinstance(raw_path, str):
            return None, {
                "success": False,
                "error_code": "invalid_directory_path",
                "error": "dir_path must resolve to text, not raw bytes.",
                "message": "Provide a text directory path for the project tree.",
            }
        if not raw_path:
            return None, {
                "success": False,
                "error_code": "invalid_directory_path",
                "error": "dir_path must not be empty.",
                "message": "Provide a non-empty directory path for the project tree.",
            }
        if isinstance(raw_path, str) and "\x00" in raw_path:
            return None, {
                "success": False,
                "error_code": "invalid_directory_path",
                "error": "dir_path must not contain NUL bytes.",
                "message": "Provide a valid directory path for the project tree.",
            }
        try:
            normalized = Path(raw_path).expanduser().absolute()
            exists = normalized.exists()
            is_directory = normalized.is_dir()
        except (OSError, RuntimeError, ValueError) as exc:
            return None, {
                "success": False,
                "error_code": "invalid_directory_path",
                "error": f"{type(exc).__name__}: {exc}",
                "message": "QZX could not normalize the requested directory path.",
            }
        if not exists:
            return None, {
                "success": False,
                "error_code": "directory_not_found",
                "error": f"Directory '{normalized}' does not exist.",
                "message": f"The requested project directory '{normalized}' was not found.",
            }
        if not is_directory:
            return None, {
                "success": False,
                "error_code": "not_a_directory",
                "error": f"'{normalized}' is not a directory.",
                "message": "Project trees require a directory path.",
            }
        return normalized, None

    @staticmethod
    def _bounded_integer(value, *, field, minimum, maximum):
        if isinstance(value, bool):
            parsed = None
        else:
            try:
                parsed = int(value)
            except (TypeError, ValueError, OverflowError):
                parsed = None
        if parsed is None or parsed < minimum or parsed > maximum:
            return None, {
                "success": False,
                "error_code": f"invalid_{field}",
                "error": (
                    f"{field} must be an integer from {minimum} through {maximum}; "
                    f"received {value!r}."
                ),
                "message": f"Choose a bounded {field} value and retry.",
            }
        return parsed, None

    @classmethod
    def _normalize_boolean(cls, value):
        if isinstance(value, bool):
            return value
        return cls._parse_bool(value)

    @staticmethod
    def _normalize_excludes(exclude_dirs):
        if exclude_dirs is None:
            names = _DEFAULT_EXCLUDES
        elif isinstance(exclude_dirs, str):
            names = exclude_dirs.split(",")
        else:
            return None, {
                "success": False,
                "error_code": "invalid_exclude_dirs",
                "error": "exclude_dirs must be one comma-separated string.",
                "message": "Provide directory names separated by commas.",
            }
        normalized = {name.strip().casefold() for name in names if name.strip()}
        return normalized, None

    @staticmethod
    def _entry_type(entry):
        is_junction = getattr(os.path, "isjunction", None)
        if entry.is_symlink() or (
            is_junction is not None and is_junction(entry.path)
        ):
            return "symlink"
        if entry.is_dir(follow_symlinks=False):
            return "directory"
        if entry.is_file(follow_symlinks=False):
            return "file"
        return "other"

    def _candidate_entries(
        self,
        entries,
        *,
        excludes,
        include_files,
        state,
    ):
        type_order = {
            "directory": 0,
            "file": 1,
            "symlink": 2,
            "other": 3,
            "unavailable": 4,
        }
        for entry in entries:
            classification_error = None
            try:
                entry_type = self._entry_type(entry)
            except OSError as exc:
                entry_type = "unavailable"
                classification_error = exc
                state.record_error(entry.path, exc)

            if entry_type == "directory" and entry.name.casefold() in excludes:
                state.excluded_directory_count += 1
                continue
            if entry_type in {"file", "other"} and not include_files:
                state.skipped_file_count += 1
                continue

            sort_key = (
                type_order[entry_type],
                entry.name.casefold(),
                entry.name,
            )
            yield sort_key, entry, entry_type, classification_error

    def _populate_directory(
        self,
        node,
        path,
        *,
        current_depth,
        max_depth,
        excludes,
        include_files,
        state,
    ):
        if current_depth >= max_depth:
            return
        if state.remaining_entries == 0:
            self._append_limit_marker(node, state)
            return

        requested = state.remaining_entries + 1
        try:
            with self._scandir(path) as entries:
                candidates = heapq.nsmallest(
                    requested,
                    self._candidate_entries(
                        entries,
                        excludes=excludes,
                        include_files=include_files,
                        state=state,
                    ),
                    key=lambda candidate: candidate[0],
                )
        except OSError as exc:
            state.record_error(path, exc)
            error = {
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
            node["scan_error"] = error
            node["children"].append(
                {
                    "name": f"[Scan failed: {type(exc).__name__}]",
                    "type": "error",
                    "error": str(exc),
                }
            )
            return

        overflow_here = len(candidates) > state.remaining_entries
        if overflow_here:
            candidates = candidates[: state.remaining_entries]

        for index, (_sort_key, entry, entry_type, error) in enumerate(candidates):
            if state.remaining_entries == 0:
                self._append_limit_marker(node, state)
                break
            child = self._entry_node(entry, entry_type, error, state)
            state.record_entry(entry_type)
            node["children"].append(child)

            if entry_type == "directory":
                self._populate_directory(
                    child,
                    Path(entry.path),
                    current_depth=current_depth + 1,
                    max_depth=max_depth,
                    excludes=excludes,
                    include_files=include_files,
                    state=state,
                )
            if state.remaining_entries == 0 and (
                index < len(candidates) - 1 or overflow_here
            ):
                self._append_limit_marker(node, state)
                break

        if overflow_here and state.remaining_entries > 0:
            self._append_limit_marker(node, state)

    def _entry_node(self, entry, entry_type, classification_error, state):
        node = {"name": entry.name, "type": entry_type}
        if entry_type == "directory":
            node["children"] = []
        elif entry_type == "file":
            try:
                node["size_bytes"] = entry.stat(follow_symlinks=False).st_size
            except OSError as exc:
                state.record_error(entry.path, exc)
                node["metadata_error"] = {
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
        elif entry_type == "symlink":
            is_junction = getattr(os.path, "isjunction", None)
            try:
                junction = bool(
                    is_junction is not None and is_junction(entry.path)
                )
            except OSError:
                junction = False
            node["link_kind"] = "junction" if junction else "symlink"
            node["followed"] = False
            try:
                node["target"] = self._readlink(entry.path)
            except OSError as exc:
                state.record_error(entry.path, exc)
                node["target_error"] = {
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
        elif entry_type == "unavailable" and classification_error is not None:
            node["error"] = {
                "error_type": type(classification_error).__name__,
                "error": str(classification_error),
            }
        return node

    @staticmethod
    def _append_limit_marker(node, state):
        state.entry_limit_reached = True
        if any(child.get("type") == "truncated" for child in node["children"]):
            return
        node["children"].append(
            {
                "name": "[Entry limit reached]",
                "type": "truncated",
            }
        )

    @classmethod
    def _render_tree(cls, root):
        lines = [cls._display_name(root)]
        cls._render_children(root.get("children", []), "", lines)
        return "\n".join(lines)

    @classmethod
    def _render_children(cls, children, prefix, lines):
        for index, child in enumerate(children):
            is_last = index == len(children) - 1
            connector = "└── " if is_last else "├── "
            lines.append(prefix + connector + cls._display_name(child))
            grand_children = child.get("children", [])
            if grand_children:
                cls._render_children(
                    grand_children,
                    prefix + ("    " if is_last else "│   "),
                    lines,
                )

    @staticmethod
    def _display_name(node):
        name = node["name"]
        if node.get("type") == "symlink":
            target = node.get("target", "[target unavailable]")
            return f"{name} -> {target} [{node.get('link_kind', 'symlink')}; not followed]"
        if node.get("type") == "other":
            return f"{name} [other filesystem entry]"
        if node.get("type") == "unavailable":
            return f"{name} [unavailable]"
        return name
