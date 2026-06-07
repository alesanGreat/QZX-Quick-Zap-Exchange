#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MakeScaffProgramPhp Command - Creates a basic scaffolding for a PHP/Composer program
"""

import os
import shutil
import datetime
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from qzx.core.command_base import CommandBase

class MakeScaffProgramPhpCommand(CommandBase):
    """
    Command to generate a basic scaffolding for a PHP/Composer program.
    Creates a new PHP project with standard directory structure and basic files.
    """
    
    name = "scaffoldPhp"
    aliases = ["phpScaff", "newPhp", "createPhp", "makeScaffProgramPhp"]
    description = "Creates a basic scaffolding for a PHP/Composer program"
    category = "development"
    
    parameters = [
        {
            'name': 'project_name',
            'description': 'Name of the PHP project to create',
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
            'description': 'Whether to include test scaffolding (phpunit)',
            'required': False,
            'default': 'true'
        }
    ]
    
    examples = [
        {
            'command': 'qzx makeScaffProgramPhp my_php_project',
            'description': 'Creates a new PHP project named "my_php_project" in the current directory'
        },
        {
            'command': 'qzx phpScaff app_service /path/to/dir true',
            'description': 'Creates a new PHP project with PHPUnit tests in the specified directory'
        }
    ]
    
    def execute(self, project_name, path='.', with_tests='true'):
        """
        Creates a basic scaffolding for a PHP program
        
        Args:
            project_name (str): Name of the PHP project to create
            path (str): Path where to create the project
            with_tests (str): Whether to include test scaffolding
            
        Returns:
            Dictionary with the operation results and status
        """
        try:
            # Convert string parameters to appropriate types
            if isinstance(with_tests, str):
                with_tests = with_tests.lower() in ('true', 'yes', 'y', '1', 't')
            
            # Normalize and validate project name
            project_name = self._normalize_project_name(project_name)
            if not project_name:
                return {
                    "success": False,
                    "error": "Invalid project name",
                    "message": "Project name cannot be empty and must contain valid characters (letters, numbers, underscores)."
                }
            
            # Ensure path exists
            if not os.path.exists(path):
                return {
                    "success": False,
                    "error": f"Path does not exist: {path}",
                    "message": f"Cannot create project: the specified path '{path}' does not exist."
                }
            
            # Determine full project path
            project_path = os.path.join(path, project_name)
            
            # Check if project directory already exists
            if os.path.exists(project_path):
                return {
                    "success": False,
                    "error": f"Project directory already exists: {project_path}",
                    "message": f"Cannot create project: directory '{project_path}' already exists."
                }
            
            # Initialize result dictionary
            result = {
                "success": True,
                "project_name": project_name,
                "project_path": project_path,
                "with_tests": with_tests,
                "files_created": [],
                "timestamp": datetime.datetime.now().isoformat(),
            }
            
            # Create project directory
            os.makedirs(project_path)
            result["files_created"].append(project_path)
            
            # Create standard PHP project structure
            src_dir = os.path.join(project_path, 'src')
            os.makedirs(src_dir)
            result["files_created"].append(src_dir)
            
            # Create files
            namespace = self._get_namespace(project_name)
            self._create_composer_json(project_path, project_name, namespace, with_tests, result)
            self._create_core_php(src_dir, namespace, result)
            self._create_index_php(project_path, namespace, result)
            self._create_gitignore(project_path, result)
            self._create_readme(project_path, project_name, with_tests, result)
            
            if with_tests:
                self._create_tests(project_path, namespace, result)
            
            # Create a descriptive message
            tests_msg = "with PHPUnit test scaffolding" if with_tests else "without tests"
            
            message = (
                f"Successfully created PHP project '{project_name}' at {project_path} {tests_msg}. "
                f"Created {len(result['files_created'])} files and directories. "
                f"Use 'composer install' and 'php index.php' to run."
            )
            
            result["message"] = message
            return result
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Error creating PHP project: {str(e)}",
                "message": f"Failed to create PHP project scaffolding: {str(e)}",
                "project_name": project_name
            }
            
    def _normalize_project_name(self, name):
        """Normalize project name for folder name and composer package name"""
        normalized = name.replace(' ', '-').replace('_', '-')
        normalized = ''.join(c for c in normalized if c.isalnum() or c == '-')
        return normalized.lower()
        
    def _get_namespace(self, project_name):
        """Converts kebab-case project name to StudlyCaps Namespace"""
        parts = project_name.split('-')
        return "".join(part.capitalize() for part in parts)
        
    def _create_composer_json(self, project_path, project_name, namespace, with_tests, result):
        composer_path = os.path.join(project_path, 'composer.json')
        
        content = f'''{{
    "name": "qzx/{project_name}",
    "description": "A PHP project created with QZX scaffolding tool",
    "type": "project",
    "autoload": {{
        "psr-4": {{
            "{namespace}\\\\": "src/"
        }}
    }}'''
    
        if with_tests:
            content += ''',
    "autoload-dev": {
        "psr-4": {
            "Tests\\\\": "tests/"
        }
    },
    "require-dev": {
        "phpunit/phpunit": "^10.0"
    }'''
            
        content += '\n}\n'
        
        with open(composer_path, 'w', encoding='utf-8') as f:
            f.write(content)
        result["files_created"].append(composer_path)
        
    def _create_core_php(self, src_dir, namespace, result):
        core_path = os.path.join(src_dir, 'Core.php')
        with open(core_path, 'w', encoding='utf-8') as f:
            f.write(f'''<?php

namespace {namespace};

class Core
{{
    public function hello(): string
    {{
        return "Hello, world from {namespace}!";
    }}

    public function add(int $a, int $b): int
    {{
        return $a + $b;
    }}
}}
''')
        result["files_created"].append(core_path)
        
    def _create_index_php(self, project_path, namespace, result):
        index_path = os.path.join(project_path, 'index.php')
        with open(index_path, 'w', encoding='utf-8') as f:
            f.write(f'''<?php

require __DIR__ . '/vendor/autoload.php';

use {namespace}\\Core;

$core = new Core();
echo $core->hello() . PHP_EOL;
''')
        result["files_created"].append(index_path)
        
    def _create_gitignore(self, project_path, result):
        gitignore_path = os.path.join(project_path, '.gitignore')
        with open(gitignore_path, 'w', encoding='utf-8') as f:
            f.write('''/vendor/
composer.lock
.DS_Store
Thumbs.db
.env
.env.local
''')
        result["files_created"].append(gitignore_path)
        
    def _create_readme(self, project_path, project_name, with_tests, result):
        readme_path = os.path.join(project_path, 'README.md')
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(f'''# {project_name.title()}

A PHP project created with QZX scaffolding tool.

## Installation

```bash
composer install
```

## Running the application

```bash
php index.php
```
''')
            if with_tests:
                f.write(f'''
## Testing

```bash
./vendor/bin/phpunit
```
''')
        result["files_created"].append(readme_path)
        
    def _create_tests(self, project_path, namespace, result):
        tests_dir = os.path.join(project_path, 'tests')
        os.makedirs(tests_dir, exist_ok=True)
        result["files_created"].append(tests_dir)
        
        # Write phpunit.xml
        phpunit_xml_path = os.path.join(project_path, 'phpunit.xml')
        with open(phpunit_xml_path, 'w', encoding='utf-8') as f:
            f.write('''<?xml version="1.0" encoding="UTF-8"?>
<phpunit xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:noNamespaceSchemaLocation="https://schema.phpunit.de/10.0/phpunit.xsd"
         bootstrap="vendor/autoload.php"
         colors="true">
    <testsuites>
        <testsuite name="Test Suite">
            <directory>tests</directory>
        </testsuite>
    </testsuites>
</phpunit>
''')
        result["files_created"].append(phpunit_xml_path)
        
        test_file_path = os.path.join(tests_dir, 'CoreTest.php')
        with open(test_file_path, 'w', encoding='utf-8') as f:
            f.write(f'''<?php

namespace Tests;

use PHPUnit\\Framework\\TestCase;
use {namespace}\\Core;

class CoreTest extends TestCase
{{
    public function testHelloReturnsGreeting()
    {{
        $core = new Core();
        $this->assertStringContainsString('Hello', $core->hello());
    }}

    public function testAddAddsTwoNumbers()
    {{
        $core = new Core();
        $this->assertEquals(5, $core->add(2, 3));
    }}
}}
''')
        result["files_created"].append(test_file_path)
