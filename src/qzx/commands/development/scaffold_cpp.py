#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ScaffoldCpp Command - Creates a basic scaffolding for a C++ program
"""

import subprocess

from qzx.commands.development._cpp_scaffold_build import (
    create_cmake_files,
    create_gitignore,
    create_makefile,
    create_readme,
    scaffold_cpp_project,
)
from qzx.commands.development._cpp_scaffold_sources import (
    create_include_directory,
    create_src_directory,
    create_tests_directory,
)
from qzx.core.command_base import CommandBase

class ScaffoldCppCommand(CommandBase):
    """
    Command to generate a basic scaffolding for a C++ program.
    Creates a new C++ project with standard directory structure and basic files.
    """
    
    name = "scaffoldCpp"
    description = "Creates a basic scaffolding for a C++ program"
    category = "development"
    
    parameters = [
        {
            'name': 'project_name',
            'description': 'Name of the C++ project to create',
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
            'description': 'Whether to include testing scaffolding (using Catch2)',
            'required': False,
            'default': True,
            'type': 'bool'
        },
        {
            'name': 'build_system',
            'description': 'Build system to use (make, cmake, or none)',
            'required': False,
            'default': 'cmake'
        },
        {
            'name': 'cpp_standard',
            'description': 'C++ standard to use (11, 14, 17, 20)',
            'required': False,
            'default': '17'
        }
    ]
    
    examples = [
        {
            'command': 'qzx scaffoldCpp my_project',
            'description': 'Creates a new C++ project using CMake in the current directory'
        },
        {
            'command': 'qzx scaffoldCpp my_project /path/to/dir true make 20',
            'description': 'Creates a new C++ project using Make, C++20 and tests in the specified directory'
        },
        {
            'command': 'qzx scaffoldCpp util_library . false none 17',
            'description': 'Creates a C++ project without tests or build system in the current directory using C++17'
        }
    ]
    
    def execute(
        self,
        project_name,
        path='.',
        with_tests=True,
        build_system='cmake',
        cpp_standard='17',
    ):
        """Create a C++ scaffold through semantic generation helpers."""
        return scaffold_cpp_project(
            self,
            project_name,
            path,
            with_tests,
            build_system,
            cpp_standard,
        )

    def _create_src_directory(self, project_path, project_name, result):
        return create_src_directory(project_path, project_name, result)

    def _create_include_directory(self, project_path, project_name, result):
        return create_include_directory(project_path, project_name, result)

    def _create_tests_directory(self, project_path, project_name, result):
        return create_tests_directory(project_path, project_name, result)

    def _create_makefile(
        self,
        project_path,
        project_name,
        with_tests,
        cpp_standard,
        result,
    ):
        return create_makefile(
            project_path,
            project_name,
            with_tests,
            cpp_standard,
            result,
        )

    def _create_cmake_files(
        self,
        project_path,
        project_name,
        with_tests,
        cpp_standard,
        result,
    ):
        return create_cmake_files(
            project_path,
            project_name,
            with_tests,
            cpp_standard,
            result,
        )

    def _create_readme(
        self,
        project_path,
        project_name,
        build_system,
        with_tests,
        cpp_standard,
        result,
    ):
        return create_readme(
            project_path,
            project_name,
            build_system,
            with_tests,
            cpp_standard,
            result,
        )

    def _create_gitignore(self, project_path, result):
        return create_gitignore(project_path, result)

    def _is_cpp_compiler_installed(self):
        """
        Check if a C++ compiler is installed
        
        Returns:
            bool: True if a C++ compiler is installed, False otherwise
        """
        # Try g++ first
        try:
            process = subprocess.run(
                ["g++", "--version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False
            )
            if process.returncode == 0:
                return True
        except FileNotFoundError:
            pass
        
        # Try clang++ next
        try:
            process = subprocess.run(
                ["clang++", "--version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False
            )
            if process.returncode == 0:
                return True
        except FileNotFoundError:
            pass
        
        # Try cl.exe for Windows
        try:
            process = subprocess.run(
                ["cl"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False
            )
            # cl.exe returns an error code even on help, but it should output something
            if process.stderr or process.stdout:
                return True
        except FileNotFoundError:
            pass
        
        return False 
