#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Read-only project health diagnosis with explicit evidence boundaries."""

from qzx.core.command_base import CommandBase

from ._diagnose_command import execute_diagnosis
from ._diagnose_dependencies import (
    dependency_name,
    dependency_record,
    inspect_dependencies,
    literal_or_assignment,
    parse_go_mod,
    parse_mapping_dependency_groups,
    parse_pyproject_dependencies,
    parse_requirements_dependencies,
    parse_setup_dependencies,
    read_document,
)
from ._diagnose_findings import build_issues, build_summary
from ._diagnose_inspection import (
    detect_technologies,
    inspect_environment,
    inspect_git,
    inspect_source,
    run_git,
    scan_large_files,
)
from ._diagnose_report import render_report


class DiagnoseProjectCommand(CommandBase):
    """Inspect project health without executing project-owned scripts."""

    name = "diagnoseProject"
    description = (
        "Inspects project technologies, dependencies, validation workflows, Git "
        "state, source quality, and large files without executing project scripts"
    )
    category = "development"
    parameters = [
        {
            "name": "path",
            "description": "Path to the project directory to diagnose (default: '.')",
            "required": False,
            "default": ".",
        }
    ]
    examples = [
        {"command": "qzx diagnoseProject", "description": "Diagnose the current project without running its scripts"},
        {"command": "qzx diagnoseProject C:/my/project", "description": "Diagnose the project at the specified path"},
    ]

    _render_report = staticmethod(render_report)
    _read_document = staticmethod(read_document)
    _detect_technologies = staticmethod(detect_technologies)
    _inspect_dependencies = inspect_dependencies
    _parse_pyproject_dependencies = parse_pyproject_dependencies
    _parse_setup_dependencies = parse_setup_dependencies
    _literal_or_assignment = staticmethod(literal_or_assignment)
    _parse_requirements_dependencies = parse_requirements_dependencies
    _parse_mapping_dependency_groups = parse_mapping_dependency_groups
    _parse_go_mod = parse_go_mod
    _dependency_record = dependency_record
    _dependency_name = staticmethod(dependency_name)
    _inspect_environment = staticmethod(inspect_environment)
    _inspect_git = inspect_git
    _run_git = staticmethod(run_git)
    _inspect_source = staticmethod(inspect_source)
    _scan_large_files = scan_large_files
    _build_issues = staticmethod(build_issues)
    _build_summary = staticmethod(build_summary)

    def execute(self, path="."):
        return execute_diagnosis(self, path)
