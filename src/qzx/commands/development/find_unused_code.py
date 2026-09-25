#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Find definitions that have no statically visible source-code references."""

from qzx.core.command_base import CommandBase

from ._unused_code_analysis import execute_unused_code_analysis
from ._unused_symbol_extractors import (
    extract_cpp_symbols,
    extract_csharp_symbols,
    extract_go_symbols,
    extract_java_symbols,
    extract_js_ts_symbols,
    extract_kotlin_symbols,
    extract_php_symbols,
    extract_python_symbols,
    extract_rust_symbols,
)


class FindUnusedCodeCommand(CommandBase):
    """Identify review candidates, not definitive dead code."""

    name = "findUnusedCode"
    description = (
        "Finds functions, classes, and exports with no statically visible "
        "references so they can be reviewed for removal"
    )
    category = "development"

    parameters = [
        {
            "name": "scan_path",
            "description": "Path to scan for files (defaults to current directory)",
            "required": False,
            "default": ".",
        }
    ]

    examples = [
        {
            "command": "qzx findUnusedCode",
            "description": "Find unused-code candidates in the current directory",
        },
        {
            "command": 'qzx findUnusedCode "src/"',
            "description": "Find unused-code candidates in the src/ directory",
        },
    ]

    SUPPORTED_EXTENSIONS = {
        ".py",
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".php",
        ".rs",
        ".cpp",
        ".hpp",
        ".cc",
        ".cxx",
        ".h",
        ".go",
        ".java",
        ".kt",
        ".cs",
    }

    _extract_python_symbols = extract_python_symbols
    _extract_js_ts_symbols = extract_js_ts_symbols
    _extract_php_symbols = extract_php_symbols
    _extract_rust_symbols = extract_rust_symbols
    _extract_cpp_symbols = extract_cpp_symbols
    _extract_go_symbols = extract_go_symbols
    _extract_java_symbols = extract_java_symbols
    _extract_kotlin_symbols = extract_kotlin_symbols
    _extract_csharp_symbols = extract_csharp_symbols

    def execute(self, scan_path="."):
        """Find definitions with no statically visible references."""
        return execute_unused_code_analysis(self, scan_path)
