#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Analyze source-code complexity for development environments."""

from qzx.core.command_base import CommandBase

from ._complexity_command import execute_complexity
from ._complexity_metrics import (
    analyze_file,
    analyze_generic,
    analyze_js_ts,
    analyze_python,
    calculate_complexity_score,
    calculate_halstead_metrics,
    calculate_maintainability_index,
    get_language_metrics,
)
from ._complexity_report import format_detailed, format_results, format_summary


class AnalyzeComplexityCommand(CommandBase):
    """Analyze complexity metrics for supported source files."""

    name = "analyzeComplexity"
    description = "Analyzes code complexity metrics for files or projects"
    category = "development"

    parameters = [
        {
            "name": "file_path",
            "description": "Path to the file or directory to analyze",
            "required": True,
        },
        {
            "name": "recursive",
            "description": (
                "Whether to recursively analyze directories: -r/--recursive for "
                "unlimited, -rN/--recursiveN for N levels"
            ),
            "required": False,
            "default": False,
        },
        {
            "name": "detail_level",
            "description": 'Detail level: "detailed" or "summary"',
            "required": False,
            "default": "detailed",
        },
    ]

    examples = [
        {
            "command": 'qzx analyzeComplexity "main.py"',
            "description": "Analyze complexity of a single Python file",
        },
        {
            "command": 'qzx analyzeComplexity "src/components" -r',
            "description": "Recursively analyze all code files in a directory",
        },
        {
            "command": 'qzx analyzeComplexity "project/" -r2 --detail-level summary',
            "description": "Generate a summary report analyzing up to 2 levels deep",
        },
    ]

    SUPPORTED_EXTENSIONS = {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".java": "java",
        ".c": "c",
        ".cpp": "cpp",
        ".h": "c",
        ".hpp": "cpp",
        ".cs": "csharp",
        ".php": "php",
        ".rb": "ruby",
        ".go": "go",
        ".rs": "rust",
    }

    _analyze_file = analyze_file
    _get_language_metrics = get_language_metrics
    _analyze_python = analyze_python
    _analyze_js_ts = analyze_js_ts
    _analyze_generic = analyze_generic
    _calculate_halstead_metrics = calculate_halstead_metrics
    _calculate_maintainability_index = calculate_maintainability_index
    _calculate_complexity_score = calculate_complexity_score
    _format_results = format_results
    _format_detailed = format_detailed
    _format_summary = format_summary

    def execute(self, file_path, recursive=False, detail_level="detailed"):
        return execute_complexity(self, file_path, recursive, detail_level)
