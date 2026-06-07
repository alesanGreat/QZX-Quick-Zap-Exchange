#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MakeScaffProgramKotlin Command - Creates a basic scaffolding for a Kotlin program
"""

import os
import subprocess
import datetime
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from qzx.core.command_base import CommandBase


class MakeScaffProgramKotlinCommand(CommandBase):
    """
    Command to generate a basic scaffolding for a Kotlin program.
    Creates a new Kotlin project with Gradle (Kotlin DSL) and JUnit 5.
    """

    name = "scaffoldKotlin"
    aliases = ["kotlinScaff", "newKotlin", "createKotlin", "makeScaffProgramKotlin"]
    description = "Creates a basic scaffolding for a Kotlin program"
    category = "development"

    parameters = [
        {
            'name': 'project_name',
            'description': 'Name of the Kotlin project to create',
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
            'description': 'Whether to include test scaffolding (JUnit 5)',
            'required': False,
            'default': 'true'
        }
    ]

    examples = [
        {
            'command': 'qzx makeScaffProgramKotlin my_project',
            'description': 'Creates a new Kotlin project named "my_project" with Gradle in the current directory'
        },
        {
            'command': 'qzx kotlinScaff backend_api /path/to/dir true',
            'description': 'Creates a new Kotlin project with tests in the specified directory'
        }
    ]

    def execute(self, project_name, path='.', with_tests='true'):
        """
        Creates a basic scaffolding for a Kotlin program
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

            result = {
                "success": True,
                "project_name": project_name,
                "project_path": project_path,
                "with_tests": with_tests,
                "files_created": [],
                "timestamp": datetime.datetime.now().isoformat(),
            }

            os.makedirs(project_path)
            result["files_created"].append(project_path)

            package_path = f"com/example/{project_name}"
            package_dir_path = package_path.replace('/', os.sep)

            self._create_settings_gradle(project_path, project_name, result)
            self._create_build_gradle(project_path, project_name, result)
            self._create_source_directory(project_path, project_name, package_dir_path, result)
            if with_tests:
                self._create_test_directory(project_path, project_name, package_dir_path, result)
            self._create_readme(project_path, project_name, result)
            self._create_gitignore(project_path, result)

            tests_msg = "with test scaffolding" if with_tests else "without tests"

            message = (
                f"Successfully created Kotlin project '{project_name}' at {project_path} "
                f"{tests_msg}. "
                f"Created {len(result['files_created'])} files and directories. "
                f"Use 'cd {project_path} && ./gradlew build' to build the project."
            )

            if not self._is_gradle_installed():
                message += " Note: Gradle doesn't appear to be installed. "
                message += "The included Gradle wrapper can be used after the first download, or install from https://gradle.org/install/."

            result["message"] = message
            return result

        except Exception as e:
            return {
                "success": False,
                "error": f"Error creating Kotlin project: {str(e)}",
                "message": f"Failed to create Kotlin project scaffolding: {str(e)}",
                "project_name": project_name
            }

    def _normalize_project_name(self, name):
        normalized = name.replace(' ', '_').replace('-', '_')
        normalized = ''.join(c for c in normalized if c.isalnum() or c == '_')
        if normalized and not (normalized[0].isalpha() or normalized[0] == '_'):
            normalized = 'kt_' + normalized
        return normalized.lower()

    def _create_settings_gradle(self, project_path, project_name, result):
        settings_path = os.path.join(project_path, 'settings.gradle.kts')
        with open(settings_path, 'w') as f:
            f.write(f'''rootProject.name = "{project_name}"
''')
        result["files_created"].append(settings_path)

    def _create_build_gradle(self, project_path, project_name, result):
        build_path = os.path.join(project_path, 'build.gradle.kts')
        with open(build_path, 'w') as f:
            f.write('''plugins {
    kotlin("jvm") version "1.9.24"
    application
}

group = "com.example"
version = "1.0-SNAPSHOT"

repositories {
    mavenCentral()
}

dependencies {
    testImplementation(kotlin("test"))
    testImplementation("org.junit.jupiter:junit-jupiter:5.10.0")
}

tasks.test {
    useJUnitPlatform()
}

kotlin {
    jvmToolchain(17)
}

application {
    mainClass.set("com.example.''' + project_name + '''.AppKt")
}
''')
        result["files_created"].append(build_path)

    def _create_source_directory(self, project_path, project_name, package_dir_path, result):
        src_dir = os.path.join(project_path, 'src', 'main', 'kotlin', package_dir_path)
        os.makedirs(src_dir)
        result["files_created"].append(src_dir)

        app_path = os.path.join(src_dir, 'App.kt')
        with open(app_path, 'w') as f:
            f.write(f'''package com.example.{project_name}

fun hello(): String {{
    return "Hello, world from {project_name}!"
}}

fun main() {{
    println(hello())
}}
''')
        result["files_created"].append(app_path)

    def _create_test_directory(self, project_path, project_name, package_dir_path, result):
        test_dir = os.path.join(project_path, 'src', 'test', 'kotlin', package_dir_path)
        os.makedirs(test_dir)
        result["files_created"].append(test_dir)

        test_path = os.path.join(test_dir, 'AppTest.kt')
        with open(test_path, 'w') as f:
            f.write(f'''package com.example.{project_name}

import org.junit.jupiter.api.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class AppTest {{
    @Test
    fun testHello() {{
        assertEquals("Hello, world from {project_name}!", hello())
    }}

    @Test
    fun testHelloContainsHello() {{
        assertTrue(hello().contains("Hello"))
    }}
}}
''')
        result["files_created"].append(test_path)

    def _create_readme(self, project_path, project_name, result):
        readme_path = os.path.join(project_path, 'README.md')
        with open(readme_path, 'w') as f:
            f.write(f'''# {project_name.replace('_', ' ').title()}

A Kotlin project created with QZX scaffolding tool.

## Build

```bash
./gradlew build
```

## Run

```bash
./gradlew run
```

## Test

```bash
./gradlew test
```
''')
        result["files_created"].append(readme_path)

    def _create_gitignore(self, project_path, result):
        gitignore_path = os.path.join(project_path, '.gitignore')
        with open(gitignore_path, 'w') as f:
            f.write('''# Gradle
.gradle/
build/
!gradle/wrapper/gradle-wrapper.jar

# Kotlin
*.class

# IDE files
.idea/
*.iml
.vscode/

# OS specific files
.DS_Store
Thumbs.db
''')
        result["files_created"].append(gitignore_path)

    def _is_gradle_installed(self):
        try:
            subprocess.run(
                ["gradle", "-v"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False
            )
            return True
        except FileNotFoundError:
            return False
