#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Build a reviewable, read-only project bootstrap plan."""

from typing import ClassVar

from qzx.core.command_base import CommandBase

from ._bootstrap_command import execute_bootstrap_plan
from ._bootstrap_selection import (
    detect_technologies,
    failure,
    root_entries,
    select_components,
    select_technology,
)
from ._bootstrap_steps import (
    check_steps,
    component_steps,
    configuration_steps,
    database_steps,
    dependency_steps,
    environment_steps,
    hook_steps,
    step,
    structure_steps,
    venv_python,
)


class PlanProjectBootstrapCommand(CommandBase):
    """Describe bootstrap work without writing files or running tools."""

    name = "planProjectBootstrap"
    description = (
        "Builds a selectable project bootstrap plan without writing files, "
        "installing dependencies, creating secrets, or running migrations"
    )
    category = "development"
    result_schema: ClassVar[dict[str, object]] = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "message": {"type": "string"},
            "error": {"type": "string"},
            "error_code": {"type": "string"},
            "details": {"type": "object", "additionalProperties": True},
        },
        "additionalProperties": True,
    }
    SUPPORTED_TECHNOLOGIES = ("python", "node", "typescript", "rust", "php", "cpp")
    COMPONENTS = ("structure", "environment", "dependencies", "configuration", "hooks", "database", "checks")
    STRUCTURE = {
        "python": ("src", "tests"), "node": ("src", "tests"),
        "typescript": ("src", "tests"), "rust": ("src", "tests"),
        "php": ("src", "tests"), "cpp": ("src", "include", "tests"),
    }
    SCAFFOLD_COMMANDS = {
        "python": "scaffoldPython", "node": "scaffoldJavaScript",
        "typescript": "scaffoldTypeScript", "rust": "scaffoldRust",
        "php": "scaffoldPhp", "cpp": "scaffoldCpp",
    }
    parameters = [
        {"name": "path", "description": "Project directory to inspect or plan", "required": False, "default": ".", "type": "str"},
        {"name": "tech", "description": "Explicit stack: python, node, typescript, rust, php, or cpp. Required when manifests do not identify exactly one stack", "required": False, "default": None, "type": "str"},
        {"name": "components", "description": "Comma-separated plan sections: structure, environment, dependencies, configuration, hooks, database, checks, or all", "required": False, "default": "all", "type": "str"},
    ]
    examples = [
        {"command": "qzx planProjectBootstrap . --tech python", "description": "Plan every Python bootstrap component without writes"},
        {"command": "qzx planProjectBootstrap ./web --tech typescript --components structure,dependencies,checks", "description": "Plan selected TypeScript bootstrap components"},
        {"command": "qzx planProjectBootstrap ./existing-project", "description": "Detect one unambiguous stack from existing manifests"},
    ]

    _root_entries = staticmethod(root_entries)
    _select_technology = classmethod(select_technology)
    _detect_technologies = staticmethod(detect_technologies)
    _select_components = classmethod(select_components)
    _component_steps = classmethod(component_steps)
    _structure_steps = classmethod(structure_steps)
    _environment_steps = classmethod(environment_steps)
    _dependency_steps = classmethod(dependency_steps)
    _configuration_steps = classmethod(configuration_steps)
    _hook_steps = classmethod(hook_steps)
    _database_steps = classmethod(database_steps)
    _check_steps = classmethod(check_steps)
    _venv_python = staticmethod(venv_python)
    _step = staticmethod(step)
    _failure = staticmethod(failure)

    def execute(self, path=".", tech=None, components="all"):
        return execute_bootstrap_plan(self, path, tech, components)
