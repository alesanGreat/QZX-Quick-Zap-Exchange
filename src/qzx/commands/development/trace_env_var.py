#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Trace one environment-variable name without exposing sensitive values."""

from qzx.commands.development._environment_trace_support import (
    detect_fallback_in_line,
    execute_environment_trace,
    parse_env_file_for_var,
)
from qzx.core.command_base import CommandBase


class TraceEnvVarCommand(CommandBase):
    """Trace environment-variable usage across supported project files."""

    name = "traceEnvVar"
    description = "Traces usage of an environment variable across code files, .env, and .env.example templates"
    category = "development"
    parameters = [
        {"name": "var_name", "description": "Name of the environment variable to search for (e.g. DATABASE_URL, PORT)", "required": True},
        {"name": "project_path", "description": "Path to the project root directory (defaults to current directory)", "required": False, "default": "."},
        {"name": "recursive", "description": "Whether to search directories recursively (defaults to True)", "required": False, "default": True},
    ]
    examples = [
        {"command": 'qzx traceEnvVar "PORT"', "description": "Trace usage of the PORT environment variable in the current directory"},
        {"command": 'qzx traceEnvVar "STRIPE_API_KEY" "C:/my-project"', "description": "Trace usage of STRIPE_API_KEY in C:/my-project"},
    ]
    SUPPORTED_EXTENSIONS = {
        ".py", ".js", ".jsx", ".ts", ".tsx", ".json", ".java", ".cs",
        ".php", ".rb", ".go", ".rs", ".sh", ".bat", ".yaml", ".yml",
        ".c", ".cpp", ".h", ".hpp", ".cc", ".cxx",
    }

    _parse_env_file_for_var = parse_env_file_for_var
    _detect_fallback_in_line = detect_fallback_in_line

    def execute(self, var_name, project_path=".", recursive=True):
        """Return masked definitions and bounded source references."""
        return execute_environment_trace(self, var_name, project_path, recursive)
