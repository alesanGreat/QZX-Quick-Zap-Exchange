#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MakeScaffProgramTypescript Command - Creates a basic scaffolding for a TypeScript program
"""

import os
import shutil
import datetime
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from qzx.core.command_base import CommandBase

class MakeScaffProgramTypescriptCommand(CommandBase):
    """
    Command to generate a basic scaffolding for a TypeScript program.
    Creates a new TypeScript project with standard directory structure and basic files.
    """
    
    name = "scaffoldTypescript"
    aliases = ["tsScaff", "newTs", "createTs", "makeScaffProgramTypescript"]
    description = "Creates a basic scaffolding for a TypeScript program"
    category = "development"
    
    parameters = [
        {
            'name': 'project_name',
            'description': 'Name of the TypeScript project to create',
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
            'description': 'Whether to include test scaffolding (jest & ts-jest)',
            'required': False,
            'default': 'true'
        }
    ]
    
    examples = [
        {
            'command': 'qzx makeScaffProgramTypescript my_ts_project',
            'description': 'Creates a new TypeScript project named "my_ts_project" in the current directory'
        },
        {
            'command': 'qzx tsScaff backend_api_ts /path/to/dir true',
            'description': 'Creates a new TypeScript project with Jest/ts-jest tests in the specified directory'
        }
    ]
    
    def execute(self, project_name, path='.', with_tests='true'):
        """
        Creates a basic scaffolding for a TypeScript program
        
        Args:
            project_name (str): Name of the TypeScript project to create
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
            
            # Create standard TypeScript project structure
            src_dir = os.path.join(project_path, 'src')
            os.makedirs(src_dir)
            result["files_created"].append(src_dir)
            
            # Create files
            self._create_package_json(project_path, project_name, with_tests, result)
            self._create_tsconfig_json(project_path, result)
            self._create_index_ts(src_dir, project_name, result)
            self._create_gitignore(project_path, result)
            self._create_readme(project_path, project_name, with_tests, result)
            
            if with_tests:
                self._create_tests(project_path, result)
            
            # Create a descriptive message
            tests_msg = "with Jest/ts-jest test scaffolding" if with_tests else "without tests"
            
            message = (
                f"Successfully created TypeScript project '{project_name}' at {project_path} {tests_msg}. "
                f"Created {len(result['files_created'])} files and directories. "
                f"Use 'npm install', 'npm run build' and 'npm start' to run."
            )
            
            result["message"] = message
            return result
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Error creating TypeScript project: {str(e)}",
                "message": f"Failed to create TypeScript project scaffolding: {str(e)}",
                "project_name": project_name
            }
            
    def _normalize_project_name(self, name):
        """Normalize project name to lowercase with hyphens for npm package compatibility"""
        normalized = name.replace(' ', '-').replace('_', '-')
        normalized = ''.join(c for c in normalized if c.isalnum() or c == '-')
        return normalized.lower()
        
    def _create_package_json(self, project_path, project_name, with_tests, result):
        pkg_path = os.path.join(project_path, 'package.json')
        
        test_script = "jest" if with_tests else "echo \\\"Error: no test specified\\\" && exit 1"
        
        content = f'''{{
  "name": "{project_name}",
  "version": "1.0.0",
  "description": "A TypeScript project created with QZX scaffolding tool",
  "main": "dist/index.js",
  "types": "dist/index.d.ts",
  "scripts": {{
    "build": "tsc",
    "start": "node dist/index.js",
    "dev": "ts-node src/index.ts",
    "test": "{test_script}"
  }},
  "keywords": [],
  "author": "",
  "license": "ISC",
  "dependencies": {{}},
  "devDependencies": {{
    "typescript": "^5.0.4",
    "@types/node": "^20.1.0",
    "ts-node": "^10.9.1"'''
  
        if with_tests:
            content += ''',
    "jest": "^29.5.0",
    "ts-jest": "^29.1.0",
    "@types/jest": "^29.5.1"'''
            
        content += '\n  }\n}\n'
        
        with open(pkg_path, 'w', encoding='utf-8') as f:
            f.write(content)
        result["files_created"].append(pkg_path)
        
    def _create_tsconfig_json(self, project_path, result):
        tsconfig_path = os.path.join(project_path, 'tsconfig.json')
        with open(tsconfig_path, 'w', encoding='utf-8') as f:
            f.write('''{
  "compilerOptions": {
    "target": "es2022",
    "module": "commonjs",
    "lib": ["es2022"],
    "declaration": true,
    "outDir": "./dist",
    "rootDir": "./src",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true
  },
  "include": ["src/**/*"],
  "exclude": ["node_modules", "dist", "tests/**/*"]
}
''')
        result["files_created"].append(tsconfig_path)
        
    def _create_index_ts(self, src_dir, project_name, result):
        index_path = os.path.join(src_dir, 'index.ts')
        with open(index_path, 'w', encoding='utf-8') as f:
            f.write(f'''// Main entry point for {project_name}

export function hello(): string {{
  return "Hello, world from {project_name}!";
}}

export function add(a: number, b: number): number {{
  return a + b;
}}

console.log(hello());
''')
        result["files_created"].append(index_path)
        
    def _create_gitignore(self, project_path, result):
        gitignore_path = os.path.join(project_path, '.gitignore')
        with open(gitignore_path, 'w', encoding='utf-8') as f:
            f.write('''node_modules/
dist/
.npm
.DS_Store
Thumbs.db
coverage/
.env
.env.local
''')
        result["files_created"].append(gitignore_path)
        
    def _create_readme(self, project_path, project_name, with_tests, result):
        readme_path = os.path.join(project_path, 'README.md')
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(f'''# {project_name.title()}

A TypeScript project created with QZX scaffolding tool.

## Installation

```bash
npm install
```

## Build

```bash
npm run build
```

## Running the application

To run the compiled production bundle:
```bash
npm start
```

To run in development mode directly:
```bash
npm run dev
```
''')
            if with_tests:
                f.write(f'''
## Testing

```bash
npm test
```
''')
        result["files_created"].append(readme_path)
        
    def _create_tests(self, project_path, result):
        tests_dir = os.path.join(project_path, 'tests')
        os.makedirs(tests_dir, exist_ok=True)
        result["files_created"].append(tests_dir)
        
        # Write jest config
        jest_config_path = os.path.join(project_path, 'jest.config.js')
        with open(jest_config_path, 'w', encoding='utf-8') as f:
            f.write('''module.exports = {
  preset: 'ts-jest',
  testEnvironment: 'node',
  testMatch: ['**/tests/**/*.test.ts'],
};
''')
        result["files_created"].append(jest_config_path)
        
        test_file_path = os.path.join(tests_dir, 'index.test.ts')
        with open(test_file_path, 'w', encoding='utf-8') as f:
            f.write('''import { hello, add } from '../src/index';

test('hello returns greeting', () => {
  expect(hello()).toContain('Hello');
});

test('add adds two numbers', () => {
  expect(add(2, 3)).toBe(5);
});
''')
        result["files_created"].append(test_file_path)
