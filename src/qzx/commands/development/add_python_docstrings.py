#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Generate documentation templates for Python code."""

from qzx.core.command_base import CommandBase

from ._python_docstring_command import (
    atomic_write_text,
    error_result,
    execute_add_python_docstrings,
    preserve_file_endings,
    validate_file_path,
)
from ._python_docstring_visitor import DocstringVisitor


class AddPythonDocstringsCommand(CommandBase):
    """Preview or add docstring templates to one Python source file."""

    name = "addPythonDocstrings"
    description = (
        "Previews or adds generated docstring templates to functions, methods, "
        "and classes in one Python file"
    )
    category = "development"
    requires_explicit_approval = True
    backup_target_parameter = "file_path"

    parameters = [
        {
            "name": "file_path",
            "description": "Path to the Python file to process",
            "required": True,
            "type": "str",
        },
        {
            "name": "style",
            "description": "Documentation style (google, numpy, sphinx)",
            "required": False,
            "default": "google",
            "type": "str",
        },
        {
            "name": "overwrite",
            "description": "Whether to overwrite existing docstrings",
            "required": False,
            "default": False,
            "type": "bool",
        },
        {
            "name": "dry_run",
            "description": "Preview changes without modifying the file",
            "required": False,
            "default": True,
            "type": "bool",
        },
    ]

    examples = [
        {
            "command": "qzx addPythonDocstrings myfile.py",
            "description": "Preview Google-style docstring templates for myfile.py",
        },
        {
            "command": "qzx addPythonDocstrings myfile.py sphinx",
            "description": "Preview Sphinx-style docstring templates for myfile.py",
        },
        {
            "command": "qzx addPythonDocstrings myfile.py --dry-run false",
            "description": "Back up myfile.py, then add missing Google-style docstrings",
        },
        {
            "command": "qzx addPythonDocstrings myfile.py --overwrite --dry-run false",
            "description": "Back up myfile.py, then replace existing docstrings",
        },
    ]

    _validate_file_path = classmethod(validate_file_path)
    _error_result = staticmethod(error_result)
    _preserve_file_endings = staticmethod(preserve_file_endings)
    _atomic_write_text = staticmethod(atomic_write_text)

    def _requested_high_risk_mutation(self, values):
        return not bool(values.get("dry_run", True))

    def validate_safety_backup_target(self, target, values):
        return self._validate_file_path(target, preview=False)

    def execute(self, file_path, style="google", overwrite=False, dry_run=True):
        return execute_add_python_docstrings(
            self, file_path, style, overwrite, dry_run
        )


__all__ = ["AddPythonDocstringsCommand", "DocstringVisitor"]
