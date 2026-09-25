#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Format supported source files through established formatter tools."""

import os

from qzx.commands.development._code_formatting_support import (
    execute_format_code,
    is_tool_available,
    run_formatter,
)
from qzx.core.command_base import CommandBase


class FormatCodeCommand(CommandBase):
    """Auto-detect source languages and invoke their formatter."""

    name = "formatCode"
    description = "Formats source code files by auto-detecting language and invoking the right formatter"
    category = "development"
    requires_explicit_approval = True
    backup_target_parameter = "path"
    parameters = [
        {"name": "path", "description": "File or directory to format", "required": True},
        {"name": "language", "description": "Force a specific language (python, javascript, typescript, rust, go, php, c, cpp). Auto-detected by default.", "required": False, "default": ""},
        {"name": "dry_run", "description": "Check if files would be changed without writing (true/false)", "required": False, "default": False},
    ]
    examples = [
        {"command": "qzx formatCode src/", "description": "Format all supported source files in src/"},
        {"command": "qzx formatCode src/main.py", "description": "Format a single Python file with black"},
        {"command": "qzx formatCode src/ python", "description": "Format only Python files in src/"},
        {"command": "qzx formatCode src/ --dry-run", "description": "Dry-run format to see which files would change"},
    ]
    FORMATTERS = {
        "python": {"extensions": {".py"}, "tool": "black", "args": ["black"], "check_args": ["black", "--check"], "fallback": None},
        "javascript": {"extensions": {".js", ".jsx", ".mjs", ".cjs"}, "tool": "prettier", "args": ["npx", "prettier", "--write"], "check_args": ["npx", "prettier", "--check"], "fallback": None},
        "typescript": {"extensions": {".ts", ".tsx"}, "tool": "prettier", "args": ["npx", "prettier", "--write"], "check_args": ["npx", "prettier", "--check"], "fallback": None},
        "rust": {"extensions": {".rs"}, "tool": "rustfmt", "args": ["rustfmt"], "check_args": ["rustfmt", "--check"], "fallback": None},
        "go": {"extensions": {".go"}, "tool": "gofmt", "args": ["gofmt", "-w"], "check_args": ["gofmt", "-l"], "fallback": None},
        "php": {"extensions": {".php"}, "tool": "php-cs-fixer", "args": ["php-cs-fixer", "fix", "--rules=@PER-CS", "--using-cache=no"], "check_args": ["php-cs-fixer", "fix", "--dry-run", "--diff", "--rules=@PER-CS", "--using-cache=no"], "fallback": None},
        "c": {"extensions": {".c", ".h"}, "tool": "clang-format", "args": ["clang-format", "-i"], "check_args": ["clang-format", "--dry-run", "--Werror"], "fallback": None},
        "cpp": {"extensions": {".cpp", ".hpp", ".cc", ".cxx"}, "tool": "clang-format", "args": ["clang-format", "-i"], "check_args": ["clang-format", "--dry-run", "--Werror"], "fallback": None},
    }
    EXTENSION_TO_LANGUAGE = {
        extension: language
        for language, configuration in FORMATTERS.items()
        for extension in configuration["extensions"]
    }
    _is_tool_available = is_tool_available
    _run_formatter = run_formatter

    def validate_safety_backup_target(self, target, values):
        """Require a real formatting target before creating its backup."""
        if not os.path.lexists(target):
            return {
                "success": False, "error_code": "path_not_found",
                "error": f"Path does not exist: {target}",
                "message": f"Path '{target}' does not exist, so no formatter was run.",
                "details": {"path": os.path.abspath(target), "dry_run": False},
            }
        return None

    def execute(self, path, language="", dry_run=False):
        """Format or check selected source files."""
        return execute_format_code(self, path, language, dry_run)
