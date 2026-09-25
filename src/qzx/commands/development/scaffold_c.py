#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ScaffoldC Command - Creates a basic scaffolding for a C program
"""

import subprocess

from qzx.commands.development._c_scaffold_build import (
    create_cmake_files,
    create_gitignore,
    create_makefile,
    create_readme,
    scaffold_c_project,
)
from qzx.commands.development._c_scaffold_sources import (
    create_include_directory,
    create_src_directory,
    create_tests_directory,
)
from qzx.core.command_base import CommandBase

class ScaffoldCCommand(CommandBase):
    """
    Command to generate a basic scaffolding for a C program.
    Creates a new C project with standard directory structure and basic files.
    """
    
    name = "scaffoldC"
    description = "Creates a basic scaffolding for a C program"
    category = "development"
    
    parameters = [
        {
            'name': 'project_name',
            'description': 'Name of the C project to create',
            'required': True
        },
        {
            'name': 'path',
            'description': 'Path where to create the project (default: current directory)',
            'required': False,
            'default': '.'
        },
        {
            'name': 'with_tests',
            'description': 'Whether to include testing scaffolding',
            'required': False,
            'default': True,
            'type': 'bool'
        },
        {
            'name': 'build_system',
            'description': 'Build system to use (make, cmake, or none)',
            'required': False,
            'default': 'make'
        }
    ]
    
    examples = [
        {
            'command': 'qzx scaffoldC my_project',
            'description': 'Creates a new C project with Makefile in the current directory'
        },
        {
            'command': 'qzx scaffoldC my_project /path/to/dir true cmake',
            'description': 'Creates a new C project with CMake and tests in the specified directory'
        },
        {
            'command': 'qzx scaffoldC network_tool . false none',
            'description': 'Creates a C project without tests or build system in the current directory'
        }
    ]
    
    def execute(self, project_name, path='.', with_tests=True, build_system='make'):
        """Create a C scaffold through semantic generation helpers."""
        return scaffold_c_project(
            self,
            project_name,
            path,
            with_tests,
            build_system,
        )

    def _create_src_directory(self, project_path, project_name, result):
        return create_src_directory(project_path, project_name, result)

    def _create_include_directory(self, project_path, project_name, result):
        return create_include_directory(project_path, project_name, result)

    def _create_tests_directory(self, project_path, project_name, result):
        return create_tests_directory(project_path, project_name, result)

    def _create_makefile(self, project_path, project_name, with_tests, result):
        return create_makefile(
            project_path,
            project_name,
            with_tests,
            result,
        )

    def _create_cmake_files(
        self,
        project_path,
        project_name,
        with_tests,
        result,
    ):
        return create_cmake_files(
            project_path,
            project_name,
            with_tests,
            result,
        )

    def _create_readme(
        self,
        project_path,
        project_name,
        build_system,
        with_tests,
        result,
    ):
        return create_readme(
            project_path,
            project_name,
            build_system,
            with_tests,
            result,
        )

    def _create_gitignore(self, project_path, result):
        return create_gitignore(project_path, result)

    def _is_gcc_installed(self):
        """
        Check if GCC is installed
        
        Returns:
            bool: True if GCC is installed, False otherwise
        """
        try:
            process = subprocess.run(
                ["gcc", "--version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False
            )
            return process.returncode == 0
        except FileNotFoundError:
            return False 
