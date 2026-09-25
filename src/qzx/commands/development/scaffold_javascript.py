#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ScaffoldJavaScript Command - Creates a basic scaffolding for a JavaScript/Node.js program
"""

import os

from ._node_scaffold_readme import node_project_readme

from ._scaffold_result_schema import starter_result_schema
from qzx.core.command_base import CommandBase
from qzx.commands.development._scaffold_utils import (
    normalize_project_name,
    parse_scaffold_boolean,
    prepare_scaffold_project,
)

class ScaffoldJavaScriptCommand(CommandBase):
    """
    Command to generate a basic scaffolding for a JavaScript/Node.js program.
    Creates a new JavaScript project with standard directory structure and basic files.
    """
    
    name = "scaffoldJavaScript"
    description = "Creates a basic scaffolding for a JavaScript/Node.js program"
    category = "development"
    result_schema = starter_result_schema(python=False)
    
    parameters = [
        {
            'name': 'project_name',
            'description': 'Name of the JavaScript project to create',
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
            'description': 'Whether to include test scaffolding (jest)',
            'required': False,
            'default': True,
            'type': 'bool'
        }
    ]
    
    examples = [
        {
            'command': 'qzx scaffoldJavaScript my_js_project',
            'description': 'Creates a new JavaScript project named "my_js_project" in the current directory'
        },
        {
            'command': 'qzx scaffoldJavaScript backend_api /path/to/dir true',
            'description': 'Creates a new JavaScript project with Jest tests in the specified directory'
        }
    ]
    
    def execute(self, project_name, path='.', with_tests=True):
        "Create a runnable project, validating options before any file writes."
        result = None
        try:
            with_tests = parse_scaffold_boolean(with_tests, "with_tests")
            project_name = normalize_project_name(
                project_name, separator="-", replacement_characters=(" ", "_"),
            )
            result = prepare_scaffold_project(
                project_name, path, {"with_tests": with_tests},
            )
            if not result["success"]:
                return result
            self._create_project_files(result["project_path"], project_name, with_tests, result)
            tests_msg = "with Jest test scaffolding" if with_tests else "without tests"
            result["message"] = (
                f"Created JavaScript project '{project_name}' at {result['project_path']} "
                f"{tests_msg}. Run 'node index.js' immediately; no dependency installation is required."
            )
            return result
        except Exception as error:
            failure = {
                "success": False, "error": str(error), "project_name": project_name,
                "message": f"Could not create JavaScript project: {error}",
            }
            if result is not None:
                failure.update(project_path=result["project_path"],
                               files_created=result["files_created"], partial=True)
            return failure

    def _create_project_files(self, project_path, project_name, with_tests, result):
        "Write the selected starter layout; no package manager is executed."
        # Create files
        self._create_package_json(project_path, project_name, with_tests, result)
        self._create_index_js(project_path, project_name, result)
        self._create_gitignore(project_path, result)
        self._create_readme(project_path, project_name, with_tests, result)
        
        if with_tests:
            self._create_tests(project_path, result)

    def _create_package_json(self, project_path, project_name, with_tests, result):
        pkg_path = os.path.join(project_path, 'package.json')
        
        test_script = "jest" if with_tests else "echo \\\"Error: no test specified\\\" && exit 1"
        
        content = f'''{{
  "name": "{project_name}",
  "version": "1.0.0",
  "type": "commonjs",
  "description": "A JavaScript project created with QZX scaffolding tool",
  "main": "index.js",
  "scripts": {{
    "start": "node index.js",
    "test": "{test_script}"
  }},
  "keywords": [],
  "author": "",
  "license": "ISC"'''
  
        if with_tests:
            content += ''',
  "devDependencies": {
    "jest": "^29.5.0"
  }'''
            
        content += '\n}\n'
        
        with open(pkg_path, 'x', encoding='utf-8') as f:
            f.write(content)
        result["files_created"].append(pkg_path)
        
    def _create_index_js(self, project_path, project_name, result):
        index_path = os.path.join(project_path, 'index.js')
        with open(index_path, 'x', encoding='utf-8') as f:
            f.write(f'''// Main entry point for {project_name}

function hello() {{
  return "Hello, world from {project_name}!";
}}

function add(a, b) {{
  return a + b;
}}

if (require.main === module) {{
  console.log(hello());
}}

module.exports = {{
  hello,
  add
}};
''')
        result["files_created"].append(index_path)
        
    def _create_gitignore(self, project_path, result):
        gitignore_path = os.path.join(project_path, '.gitignore')
        with open(gitignore_path, 'x', encoding='utf-8') as f:
            f.write('''node_modules/
.npm
.DS_Store
Thumbs.db
coverage/
.env
.env.local
''')
        result["files_created"].append(gitignore_path)
        
    def _create_readme(self, project_path, project_name, with_tests, result):
        content = node_project_readme(project_name, with_tests, typescript=False)
        readme_path = os.path.join(project_path, 'README.md')
        with open(readme_path, 'x', encoding='utf-8') as stream:
            stream.write(content)
        result["files_created"].append(readme_path)

    def _create_tests(self, project_path, result):
        tests_dir = os.path.join(project_path, 'tests')
        os.makedirs(tests_dir, exist_ok=True)
        result["files_created"].append(tests_dir)
        
        test_file_path = os.path.join(tests_dir, 'index.test.js')
        with open(test_file_path, 'x', encoding='utf-8') as f:
            f.write('''const { hello, add } = require('../index');

test('hello returns greeting', () => {
  expect(hello()).toContain('Hello');
});

test('add adds two numbers', () => {
  expect(add(2, 3)).toBe(5);
});
''')
        result["files_created"].append(test_file_path)
