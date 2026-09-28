#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ScaffoldRust Command - Creates a basic scaffolding for a Rust program
"""

from qzx.commands.development._rust_scaffold import (
    build_success_message,
    cargo_installed,
    create_cargo_toml,
    create_gitignore,
    create_readme,
    create_src_directory,
    create_tests_directory,
    normalize_rust_project_name,
    populate_rust_project,
)
from qzx.core.command_base import CommandBase
from qzx.commands.development._scaffold_utils import (
    parse_scaffold_boolean,
    prepare_scaffold_project,
)

class ScaffoldRustCommand(CommandBase):
    """
    Command to generate a basic scaffolding for a Rust program.
    Creates a new Rust project with standard directory structure and basic files.
    """
    
    name = "scaffoldRust"
    description = "Creates a basic scaffolding for a Rust program"
    category = "development"
    
    parameters = [
        {
            'name': 'project_name',
            'description': 'Name of the Rust project to create',
            'required': True
        },
        {
            'name': 'path',
            'description': 'Path where to create the project (default: current directory)',
            'required': False,
            'default': '.'
        },
        {
            'name': 'binary',
            'description': 'Whether to create a binary application (true) or a library (false)',
            'required': False,
            'default': True,
            'type': 'bool'
        },
        {
            'name': 'with_tests',
            'description': 'Whether to include test scaffolding',
            'required': False,
            'default': True,
            'type': 'bool'
        }
    ]
    
    examples = [
        {
            'command': 'qzx scaffoldRust my_project',
            'description': 'Creates a new Rust binary project named "my_project" in the current directory'
        },
        {
            'command': 'qzx scaffoldRust my_library false',
            'description': 'Creates a new Rust library project named "my_library" in the current directory'
        },
        {
            'command': 'qzx scaffoldRust my_project /path/to/dir true false',
            'description': 'Creates a new Rust binary project without tests in the specified directory'
        }
    ]
    
    def execute(self, project_name, path='.', binary=True, with_tests=True):
        """Create a basic Rust scaffold."""
        try:
            binary = parse_scaffold_boolean(binary, "binary")
            with_tests = parse_scaffold_boolean(with_tests, "with_tests")
            project_name = self._normalize_project_name(project_name)
            result = prepare_scaffold_project(
                project_name,
                path,
                {
                    "project_type": "binary" if binary else "library",
                    "with_tests": with_tests,
                },
            )
            if not result["success"]:
                return result
            return populate_rust_project(
                self,
                project_name,
                binary,
                with_tests,
                result,
            )
        except Exception as exc:
            return {
                "success": False,
                "error": f"Error creating Rust project: {str(exc)}",
                "message": (
                    f"Failed to create Rust project scaffolding: {str(exc)}"
                ),
                "project_name": project_name,
            }

    def _normalize_project_name(self, name):
        """Preserve the historical Rust project-name normalization hook."""
        return normalize_rust_project_name(name)

    def _create_src_directory(self, project_path, is_binary, result):
        """Preserve the source-generation hook."""
        return create_src_directory(project_path, is_binary, result)

    def _create_tests_directory(self, project_path, result):
        """Preserve the integration-test generation hook."""
        return create_tests_directory(project_path, result)

    def _create_cargo_toml(
        self,
        project_path,
        project_name,
        is_binary,
        result,
    ):
        """Preserve the Cargo manifest generation hook."""
        return create_cargo_toml(
            project_path,
            project_name,
            is_binary,
            result,
        )

    def _create_gitignore(self, project_path, result):
        """Preserve the .gitignore generation hook."""
        return create_gitignore(project_path, result)

    def _create_readme(self, project_path, project_name, is_binary, result):
        """Preserve the README generation hook."""
        return create_readme(
            project_path,
            project_name,
            is_binary,
            result,
        )

    def _build_success_message(
        self,
        project_name,
        project_path,
        binary,
        with_tests,
        result,
    ):
        """Build the scaffold result while preserving the Cargo probe hook."""
        return build_success_message(
            project_name,
            project_path,
            binary,
            with_tests,
            result,
            self._is_cargo_installed,
        )

    def _is_cargo_installed(self, runner=None):
        """Preserve the Cargo availability hook."""
        return cargo_installed(runner=runner)
