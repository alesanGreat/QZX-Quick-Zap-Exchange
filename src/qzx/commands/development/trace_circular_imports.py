#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Detect circular imports in a bounded Python source tree."""

from qzx.commands.development._import_cycle_analysis import (
    execute_import_cycle_trace,
    find_cycles,
    parse_file_imports,
)
from qzx.core.command_base import CommandBase


class TraceCircularImportsCommand(CommandBase):
    """Detect circular dependencies between Python modules."""

    name = "traceCircularImports"
    description = "Traces module imports recursively and identifies circular import dependencies (loops)"
    category = "development"
    parameters = [{
        "name": "scan_path",
        "description": "Path to scan for Python files (defaults to current directory)",
        "required": False,
        "default": ".",
    }]
    examples = [
        {"command": "qzx traceCircularImports", "description": "Search for circular imports in the current directory"},
        {"command": 'qzx traceCircularImports "src/qzx"', "description": "Search for circular imports specifically inside src/qzx"},
    ]

    _parse_file_imports = parse_file_imports
    _find_cycles = find_cycles

    def execute(self, scan_path="."):
        """Analyze Python imports below ``scan_path``."""
        return execute_import_cycle_trace(self, scan_path)
