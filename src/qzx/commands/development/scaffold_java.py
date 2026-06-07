#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MakeScaffProgramJava Command - Creates a basic scaffolding for a Java program
"""

import os
import subprocess
import datetime
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from qzx.core.command_base import CommandBase


class MakeScaffProgramJavaCommand(CommandBase):
    """
    Command to generate a basic scaffolding for a Java program.
    Creates a new Java project with Maven and JUnit 5.
    """

    name = "scaffoldJava"
    aliases = ["javaScaff", "newJava", "createJava", "makeScaffProgramJava"]
    description = "Creates a basic scaffolding for a Java program"
    category = "development"

    parameters = [
        {
            'name': 'project_name',
            'description': 'Name of the Java project to create',
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
        },
        {
            'name': 'build_tool',
            'description': 'Build tool to use (maven)',
            'required': False,
            'default': 'maven'
        }
    ]

    examples = [
        {
            'command': 'qzx makeScaffProgramJava my_project',
            'description': 'Creates a new Java project named "my_project" with Maven in the current directory'
        },
        {
            'command': 'qzx makeScaffProgramJava my_project /path/to/dir true',
            'description': 'Creates a new Java project with tests in the specified directory'
        }
    ]

    def execute(self, project_name, path='.', with_tests='true', build_tool='maven'):
        """
        Creates a basic scaffolding for a Java program
        """
        try:
            if isinstance(with_tests, str):
                with_tests = with_tests.lower() in ('true', 'yes', 'y', '1', 't')

            build_tool = build_tool.lower()
            if build_tool not in ('maven',):
                return {
                    "success": False,
                    "error": f"Unsupported build tool: {build_tool}",
                    "message": "Currently only 'maven' is supported as build tool for Java scaffolding."
                }

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
                "build_tool": build_tool,
                "files_created": [],
                "timestamp": datetime.datetime.now().isoformat(),
            }

            os.makedirs(project_path)
            result["files_created"].append(project_path)

            package_path = f"com/example/{project_name}"
            package_dir_path = package_path.replace('/', os.sep)

            self._create_pom_xml(project_path, project_name, result)
            self._create_source_directory(project_path, project_name, package_dir_path, result)
            if with_tests:
                self._create_test_directory(project_path, project_name, package_dir_path, result)
            self._create_readme(project_path, project_name, result)
            self._create_gitignore(project_path, result)

            tests_msg = "with test scaffolding" if with_tests else "without tests"

            message = (
                f"Successfully created Java project '{project_name}' at {project_path} "
                f"{tests_msg}. "
                f"Created {len(result['files_created'])} files and directories. "
                f"Use 'cd {project_path} && mvn compile' to build the project."
            )

            if not self._is_maven_installed():
                message += " Note: Maven doesn't appear to be installed. "
                message += "Install from https://maven.apache.org/install.html to build the project."

            result["message"] = message
            return result

        except Exception as e:
            return {
                "success": False,
                "error": f"Error creating Java project: {str(e)}",
                "message": f"Failed to create Java project scaffolding: {str(e)}",
                "project_name": project_name
            }

    def _normalize_project_name(self, name):
        normalized = name.replace(' ', '_').replace('-', '_')
        normalized = ''.join(c for c in normalized if c.isalnum() or c == '_')
        if normalized and not (normalized[0].isalpha() or normalized[0] == '_'):
            normalized = 'java_' + normalized
        return normalized.lower()

    def _create_pom_xml(self, project_path, project_name, result):
        pom_path = os.path.join(project_path, 'pom.xml')
        with open(pom_path, 'w') as f:
            f.write(f'''<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
                             http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <groupId>com.example</groupId>
    <artifactId>{project_name}</artifactId>
    <version>1.0-SNAPSHOT</version>
    <packaging>jar</packaging>

    <properties>
        <maven.compiler.source>17</maven.compiler.source>
        <maven.compiler.target>17</maven.compiler.target>
        <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
        <junit.jupiter.version>5.10.0</junit.jupiter.version>
    </properties>

    <dependencies>
        <dependency>
            <groupId>org.junit.jupiter</groupId>
            <artifactId>junit-jupiter</artifactId>
            <version>${{junit.jupiter.version}}</version>
            <scope>test</scope>
        </dependency>
    </dependencies>

    <build>
        <plugins>
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-surefire-plugin</artifactId>
                <version>3.1.2</version>
            </plugin>
        </plugins>
    </build>
</project>
''')
        result["files_created"].append(pom_path)

    def _create_source_directory(self, project_path, project_name, package_dir_path, result):
        src_dir = os.path.join(project_path, 'src', 'main', 'java', package_dir_path)
        os.makedirs(src_dir)
        result["files_created"].append(src_dir)

        app_path = os.path.join(src_dir, 'App.java')
        class_name = self._to_class_name(project_name)
        with open(app_path, 'w') as f:
            f.write(f'''package com.example.{project_name};

public class {class_name} {{
    public static String hello() {{
        return "Hello, world from {project_name}!";
    }}

    public static void main(String[] args) {{
        System.out.println(hello());
    }}
}}
''')
        result["files_created"].append(app_path)

    def _create_test_directory(self, project_path, project_name, package_dir_path, result):
        test_dir = os.path.join(project_path, 'src', 'test', 'java', package_dir_path)
        os.makedirs(test_dir)
        result["files_created"].append(test_dir)

        test_path = os.path.join(test_dir, 'AppTest.java')
        class_name = self._to_class_name(project_name)
        with open(test_path, 'w') as f:
            f.write(f'''package com.example.{project_name};

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

public class {class_name}Test {{
    @Test
    public void testHello() {{
        String result = {class_name}.hello();
        assertEquals("Hello, world from {project_name}!", result);
    }}

    @Test
    public void testHelloContainsWorld() {{
        assertTrue({class_name}.hello().contains("Hello"));
    }}
}}
''')
        result["files_created"].append(test_path)

    def _create_readme(self, project_path, project_name, result):
        readme_path = os.path.join(project_path, 'README.md')
        with open(readme_path, 'w') as f:
            f.write(f'''# {project_name.replace('_', ' ').title()}

A Java project created with QZX scaffolding tool.

## Build

```bash
mvn compile
```

## Run

```bash
mvn exec:java -Dexec.mainClass="com.example.{project_name}.App"
```

## Test

```bash
mvn test
```
''')
        result["files_created"].append(readme_path)

    def _create_gitignore(self, project_path, result):
        gitignore_path = os.path.join(project_path, '.gitignore')
        with open(gitignore_path, 'w') as f:
            f.write('''# Compiled class files
*.class

# Maven target directory
target/

# IDE files
.idea/
*.iml
.vscode/

# OS specific files
.DS_Store
Thumbs.db
''')
        result["files_created"].append(gitignore_path)

    def _to_class_name(self, project_name):
        """Convert snake_case project name to PascalCase class name."""
        return ''.join(word.capitalize() for word in project_name.split('_'))

    def _is_maven_installed(self):
        try:
            subprocess.run(
                ["mvn", "-version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False
            )
            return True
        except FileNotFoundError:
            return False
