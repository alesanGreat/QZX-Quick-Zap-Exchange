#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Generate one bounded, symlink-safe project tree from a single scan."""

import os

from qzx.core.command_base import CommandBase

from ._project_tree_command import execute_project_tree
from ._project_tree_model import (
    DEFAULT_EXCLUDES_TEXT,
    _TreeScanState,
    bounded_integer,
    normalize_boolean,
    normalize_directory,
    normalize_excludes,
)
from ._project_tree_scan import (
    append_limit_marker,
    candidate_entries,
    display_name,
    entry_node,
    entry_type,
    populate_directory,
    render_children,
    render_tree,
)


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
            "description": "Comma-separated directory names to exclude; matching is case-insensitive",
            "required": False,
            "default": DEFAULT_EXCLUDES_TEXT,
            "type": "str",
        },
        {
            "name": "include_files",
            "description": "List regular files as well as directories; links are always listed but never followed",
            "required": False,
            "default": True,
            "type": "bool",
        },
        {
            "name": "max_entries",
            "description": "Maximum retained descendants from 1 through 100000 (defaults to 10000)",
            "required": False,
            "default": 10_000,
            "type": "int",
        },
    ]

    examples = [
        {"command": "qzx getProjectTree", "description": "Show the current project through two descendant levels"},
        {"command": "qzx getProjectTree src 3", "description": "Show the src tree through three descendant levels"},
        {"command": "qzx getProjectTree . 2 .git,node_modules false --max_entries 500", "description": "Show at most 500 directory/link entries while excluding two names"},
    ]

    _normalize_directory = staticmethod(normalize_directory)
    _bounded_integer = staticmethod(bounded_integer)
    _normalize_boolean = classmethod(normalize_boolean)
    _normalize_excludes = staticmethod(normalize_excludes)
    _entry_type = entry_type
    _candidate_entries = candidate_entries
    _populate_directory = populate_directory
    _entry_node = entry_node
    _append_limit_marker = append_limit_marker
    _render_tree = classmethod(render_tree)
    _render_children = classmethod(render_children)
    _display_name = staticmethod(display_name)

    def __init__(self, *, scandir=None, readlink=None):
        super().__init__()
        self._scandir = scandir or os.scandir
        self._readlink = readlink or os.readlink

    def execute(self, dir_path=".", max_depth=2, exclude_dirs=None, include_files=True, max_entries=10_000):
        return execute_project_tree(
            self, dir_path, max_depth, exclude_dirs, include_files, max_entries
        )


__all__ = ["GetProjectTreeCommand", "_TreeScanState"]
