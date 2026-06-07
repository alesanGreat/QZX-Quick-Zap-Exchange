#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MakeScaffProgramGo Command - Creates a basic scaffolding for a Go program
"""

import os
import subprocess
import datetime
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from qzx.core.command_base import CommandBase


class MakeScaffProgramGoCommand(CommandBase):
    """
    Command to generate a basic scaffolding for a Go program.
    Creates a new Go project with standard directory structure and basic files.
    """

    name = "scaffoldGo"
    aliases = ["goScaff", "newGo", "createGo", "makeScaffProgramGo"]
    description = "Creates a basic scaffolding for a Go program"
    category = "development"

    parameters = [
        {
            'name': 'project_name',
            'description': 'Name of the Go project to create',
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
            'description': 'Whether to include test scaffolding (Go native tests)',
            'required': False,
            'default': 'true'
        },
        {
            'name': 'module_path',
            'description': 'Go module path (default: github.com/user/{project_name})',
            'required': False,
            'default': ''
        }
    ]

    examples = [
        {
            'command': 'qzx makeScaffProgramGo my_project',
            'description': 'Creates a new Go project named "my_project" in the current directory'
        },
        {
            'command': 'qzx makeScaffProgramGo my_project /path/to/dir true github.com/example/my_project',
            'description': 'Creates a new Go project with custom module path in the specified directory'
        },
        {
            'command': 'qzx goScaff api_service . false',
            'description': 'Creates a new Go project named "api_service" without tests'
        }
    ]

    def execute(self, project_name, path='.', with_tests='true', module_path=''):
        """
        Creates a basic scaffolding for a Go program

        Args:
            project_name (str): Name of the Go project to create
            path (str): Path where to create the project
            with_tests (str): Whether to include test scaffolding
            module_path (str): Go module path

        Returns:
            Dictionary with the operation results and status
        """
        try:
            if isinstance(with_tests, str):
                with_tests = with_tests.lower() in ('true', 'yes', 'y', '1', 't')

            project_name = self._normalize_project_name(project_name)
            if not project_name:
                return {
                    "success": False,
                    "error": "Invalid project name",
                    "message": "Project name cannot be empty and must contain valid characters (letters, numbers, underscores)."
                }

            if not os.path.exists(path):
                return {
                    "success": False,
                    "error": f"Path does not exist: {path}",
                    "message": f"Cannot create project: the specified path '{path}' does not exist."
                }

            project_path = os.path.join(path, project_name)

            if os.path.exists(project_path):
                return {
                    "success": False,
                    "error": f"Project directory already exists: {project_path}",
                    "message": f"Cannot create project: directory '{project_path}' already exists."
                }

            if not module_path:
                module_path = f"github.com/user/{project_name}"

            result = {
                "success": True,
                "project_name": project_name,
                "project_path": project_path,
                "module_path": module_path,
                "with_tests": with_tests,
                "files_created": [],
                "timestamp": datetime.datetime.now().isoformat(),
            }

            os.makedirs(project_path)
            result["files_created"].append(project_path)

            self._create_go_mod(project_path, module_path, result)
            self._create_main_go(project_path, project_name, result)
            if with_tests:
                self._create_tests(project_path, project_name, result)
            self._create_readme(project_path, project_name, module_path, result)
            self._create_gitignore(project_path, result)

            tests_msg = "with test scaffolding" if with_tests else "without tests"

            message = (
                f"Successfully created Go project '{project_name}' at {project_path} "
                f"{tests_msg}. "
                f"Created {len(result['files_created'])} files and directories. "
                f"Use 'cd {project_path} && go build' to build the project."
            )

            if not self._is_go_installed():
                message += " Note: Go doesn't appear to be installed. "
                message += "Install from https://go.dev/dl/ to build the project."

            result["message"] = message
            return result

        except Exception as e:
            return {
                "success": False,
                "error": f"Error creating Go project: {str(e)}",
                "message": f"Failed to create Go project scaffolding: {str(e)}",
                "project_name": project_name
            }

    def _normalize_project_name(self, name):
        """
        Normalize project name to follow Go naming conventions
        """
        normalized = name.replace(' ', '_').replace('-', '_')
        normalized = ''.join(c for c in normalized if c.isalnum() or c == '_')
        if normalized and not (normalized[0].isalpha() or normalized[0] == '_'):
            normalized = 'go_' + normalized
        return normalized.lower()

    def _create_go_mod(self, project_path, module_path, result):
        go_mod_path = os.path.join(project_path, 'go.mod')
        with open(go_mod_path, 'w') as f:
            f.write(f'''module {module_path}

go 1.22
''')
        result["files_created"].append(go_mod_path)

    def _create_main_go(self, project_path, project_name, result):
        main_path = os.path.join(project_path, 'main.go')
        with open(main_path, 'w') as f:
            f.write(f'''package main

import "fmt"

// Hello returns a greeting message for the project.
func Hello() string {{
	return "Hello, world from {project_name}!"
}}

func main() {{
	fmt.Println(Hello())
}}
''')
        result["files_created"].append(main_path)

    def _create_tests(self, project_path, project_name, result):
        test_path = os.path.join(project_path, 'main_test.go')
        with open(test_path, 'w') as f:
            f.write(f'''package main

import "testing"

func TestHello(t *testing.T) {{
	got := Hello()
	want := "Hello, world from {project_name}!"
	if got != want {{
		t.Errorf("Hello() = %q, want %q", got, want)
	}}
}}
''')
        result["files_created"].append(test_path)

    def _create_readme(self, project_path, project_name, module_path, result):
        readme_path = os.path.join(project_path, 'README.md')
        with open(readme_path, 'w') as f:
            f.write(f'''# {project_name.replace('_', ' ').title()}

A Go project created with QZX scaffolding tool.

## Module

```
{module_path}
```

## Build

```bash
go build
```

## Run

```bash
go run .
```

## Test

```bash
go test ./...
```
''')
        result["files_created"].append(readme_path)

    def _create_gitignore(self, project_path, result):
        gitignore_path = os.path.join(project_path, '.gitignore')
        with open(gitignore_path, 'w') as f:
            f.write('''# Binaries for programs and plugins
*.exe
*.exe~
*.dll
*.so
*.dylib

# Test binary, built with `go test -c`
*.test

# Output of the go coverage tool, specifically when used with LiteIDE
*.out

# Dependency directories (remove the comment below to include it)
# vendor/

# Go workspace file
go.work
''')
        result["files_created"].append(gitignore_path)

    def _is_go_installed(self):
        try:
            subprocess.run(
                ["go", "version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False
            )
            return True
        except FileNotFoundError:
            return False
