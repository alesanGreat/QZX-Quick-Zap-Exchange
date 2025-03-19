#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MakeScaffProgramPython Command - Creates a basic scaffolding for a Python program
"""

import os
import shutil
import subprocess
import datetime
from Core.command_base import CommandBase

class MakeScaffProgramPythonCommand(CommandBase):
    """
    Command to generate a basic scaffolding for a Python program.
    Creates a new Python project with standard directory structure and basic files.
    """
    
    name = "makeScaffProgramPython"
    aliases = ["pythonScaff", "newPython", "createPython"]
    description = "Creates a basic scaffolding for a Python program"
    category = "development"
    
    parameters = [
        {
            'name': 'project_name',
            'description': 'Name of the Python project to create',
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
            'description': 'Whether to include test scaffolding (pytest)',
            'required': False,
            'default': 'true'
        },
        {
            'name': 'create_venv',
            'description': 'Whether to create a virtual environment',
            'required': False,
            'default': 'false'
        }
    ]
    
    examples = [
        {
            'command': 'qzx makeScaffProgramPython my_project',
            'description': 'Creates a new Python project named "my_project" in the current directory'
        },
        {
            'command': 'qzx makeScaffProgramPython my_project /path/to/dir true true',
            'description': 'Creates a new Python project with tests and virtual environment in the specified directory'
        },
        {
            'command': 'qzx pythonScaff api_service . false',
            'description': 'Creates a new Python project named "api_service" without tests in the current directory'
        }
    ]
    
    def execute(self, project_name, path='.', with_tests='true', create_venv='false'):
        """
        Creates a basic scaffolding for a Python program
        
        Args:
            project_name (str): Name of the Python project to create
            path (str): Path where to create the project
            with_tests (str): Whether to include test scaffolding
            create_venv (str): Whether to create a virtual environment
            
        Returns:
            Dictionary with the operation results and status
        """
        try:
            # Convert string parameters to appropriate types
            if isinstance(with_tests, str):
                with_tests = with_tests.lower() in ('true', 'yes', 'y', '1', 't')
            
            if isinstance(create_venv, str):
                create_venv = create_venv.lower() in ('true', 'yes', 'y', '1', 't')
            
            # Normalize and validate project name (convert spaces to underscores, etc.)
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
                "create_venv": create_venv,
                "files_created": [],
                "timestamp": datetime.datetime.now().isoformat(),
            }
            
            # Create project directory
            os.makedirs(project_path)
            result["files_created"].append(project_path)
            
            # Create standard Python project structure
            self._create_package_directory(project_path, project_name, result)
            
            if with_tests:
                self._create_tests_directory(project_path, project_name, result)
            
            # Create project files
            self._create_readme(project_path, project_name, result)
            self._create_setup_py(project_path, project_name, result)
            self._create_requirements_txt(project_path, result)
            self._create_gitignore(project_path, result)
            self._create_main_script(project_path, project_name, result)
            
            # Create virtual environment if requested
            if create_venv:
                venv_result = self._create_virtual_environment(project_path, result)
                # If venv creation failed, add a warning but continue
                if not venv_result["success"]:
                    result["venv_warning"] = venv_result["error"]
            
            # Create a descriptive message
            tests_msg = "with test scaffolding" if with_tests else "without tests"
            venv_msg = "and virtual environment" if create_venv else ""
            
            message = (
                f"Successfully created Python project '{project_name}' at {project_path} "
                f"{tests_msg} {venv_msg}. "
                f"Created {len(result['files_created'])} files and directories."
            )
            
            if create_venv and "venv_warning" in result:
                message += f" Note: Virtual environment creation failed: {result['venv_warning']}"
            
            # Check if pip and other tools are installed
            if not self._is_pip_installed():
                message += " Note: pip doesn't appear to be installed properly. "
                message += "You may need to install it to manage dependencies."
            
            result["message"] = message
            return result
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Error creating Python project: {str(e)}",
                "message": f"Failed to create Python project scaffolding: {str(e)}",
                "project_name": project_name
            }
    
    def _normalize_project_name(self, name):
        """
        Normalize project name to follow Python naming conventions
        
        Args:
            name (str): Raw project name
            
        Returns:
            str: Normalized project name
        """
        # Replace spaces and hyphens with underscores
        normalized = name.replace(' ', '_').replace('-', '_')
        # Remove invalid characters
        normalized = ''.join(c for c in normalized if c.isalnum() or c == '_')
        # Ensure the name starts with a letter or underscore (Python convention)
        if normalized and not (normalized[0].isalpha() or normalized[0] == '_'):
            normalized = 'py_' + normalized
        return normalized.lower()
    
    def _create_package_directory(self, project_path, project_name, result):
        """
        Create package directory with initial Python files
        
        Args:
            project_path (str): Path to the project
            project_name (str): Name of the project
            result (dict): Result dictionary to update
        """
        # Create the main package directory
        package_dir = os.path.join(project_path, project_name)
        os.makedirs(package_dir)
        result["files_created"].append(package_dir)
        
        # Create __init__.py file
        init_path = os.path.join(package_dir, '__init__.py')
        with open(init_path, 'w') as f:
            f.write(f'''"""
{project_name} package.

This package provides functionality for ...
"""

__version__ = "0.1.0"
''')
        result["files_created"].append(init_path)
        
        # Create a module file
        module_path = os.path.join(package_dir, 'core.py')
        with open(module_path, 'w') as f:
            f.write(f'''"""
Core functionality for {project_name}.
"""

def hello():
    """
    Return a greeting message.
    
    Returns:
        str: A greeting message
    """
    return "Hello, world from {project_name}!"

def add(a, b):
    """
    Add two numbers.
    
    Args:
        a: First number
        b: Second number
        
    Returns:
        The sum of a and b
    """
    return a + b
''')
        result["files_created"].append(module_path)
    
    def _create_tests_directory(self, project_path, project_name, result):
        """
        Create tests directory with pytest files
        
        Args:
            project_path (str): Path to the project
            project_name (str): Name of the project
            result (dict): Result dictionary to update
        """
        # Create tests directory
        tests_dir = os.path.join(project_path, 'tests')
        os.makedirs(tests_dir)
        result["files_created"].append(tests_dir)
        
        # Create __init__.py file
        init_path = os.path.join(tests_dir, '__init__.py')
        with open(init_path, 'w') as f:
            f.write('# Test package')
        result["files_created"].append(init_path)
        
        # Create a test file
        test_path = os.path.join(tests_dir, 'test_core.py')
        with open(test_path, 'w') as f:
            f.write(f'''"""
Tests for {project_name}.core module.
"""

import pytest
from {project_name}.core import hello, add

def test_hello():
    """Test the hello function."""
    assert isinstance(hello(), str)
    assert "Hello" in hello()

def test_add():
    """Test the add function."""
    assert add(1, 2) == 3
    assert add(5, 7) == 12
    assert add(-1, 1) == 0
    assert add(0, 0) == 0
''')
        result["files_created"].append(test_path)
        
        # Create pytest.ini
        pytest_ini_path = os.path.join(project_path, 'pytest.ini')
        with open(pytest_ini_path, 'w') as f:
            f.write(f'''[pytest]
testpaths = tests
python_files = test_*.py
python_functions = test_*
''')
        result["files_created"].append(pytest_ini_path)
    
    def _create_readme(self, project_path, project_name, result):
        """
        Create README.md file
        
        Args:
            project_path (str): Path to the project
            project_name (str): Name of the project
            result (dict): Result dictionary to update
        """
        readme_path = os.path.join(project_path, 'README.md')
        with open(readme_path, 'w') as f:
            f.write(f'''# {project_name.replace('_', ' ').title()}

A Python project created with QZX scaffolding tool.

## Installation

```bash
pip install -e .
```

## Usage

```python
import {project_name}

# Use the package
{project_name}.core.hello()
```

## Development

### Setup

```bash
# Create and activate virtual environment (optional)
python -m venv venv
source venv/bin/activate  # On Windows: venv\\Scripts\\activate

# Install development dependencies
pip install -e ".[dev]"
```

### Running Tests

```bash
pytest
```
''')
        result["files_created"].append(readme_path)
    
    def _create_setup_py(self, project_path, project_name, result):
        """
        Create setup.py file
        
        Args:
            project_path (str): Path to the project
            project_name (str): Name of the project
            result (dict): Result dictionary to update
        """
        setup_path = os.path.join(project_path, 'setup.py')
        with open(setup_path, 'w') as f:
            f.write(f'''from setuptools import setup, find_packages

setup(
    name="{project_name}",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        # Add your dependencies here
    ],
    extras_require={{
        "dev": [
            "pytest>=7.0.0",
            "black>=22.1.0",
            "flake8>=4.0.1",
        ],
    }},
    author="",
    author_email="",
    description="A Python project created with QZX scaffolding tool",
    keywords="{project_name}, python",
    python_requires=">=3.6",
)
''')
        result["files_created"].append(setup_path)
    
    def _create_requirements_txt(self, project_path, result):
        """
        Create requirements.txt file
        
        Args:
            project_path (str): Path to the project
            result (dict): Result dictionary to update
        """
        req_path = os.path.join(project_path, 'requirements.txt')
        with open(req_path, 'w') as f:
            f.write('''# Add your dependencies here
# or use setup.py for distribution

# Development tools
pytest>=7.0.0
black>=22.1.0
flake8>=4.0.1
''')
        result["files_created"].append(req_path)
    
    def _create_gitignore(self, project_path, result):
        """
        Create .gitignore file
        
        Args:
            project_path (str): Path to the project
            result (dict): Result dictionary to update
        """
        gitignore_path = os.path.join(project_path, '.gitignore')
        with open(gitignore_path, 'w') as f:
            f.write('''# Byte-compiled / optimized / DLL files
__pycache__/
*.py[cod]
*$py.class

# Distribution / packaging
dist/
build/
*.egg-info/

# Unit test / coverage reports
htmlcov/
.coverage
.pytest_cache/

# Virtual environments
venv/
env/
ENV/

# IDE files
.idea/
.vscode/
*.swp
*.swo

# OS specific files
.DS_Store
Thumbs.db
''')
        result["files_created"].append(gitignore_path)
    
    def _create_main_script(self, project_path, project_name, result):
        """
        Create a main script file
        
        Args:
            project_path (str): Path to the project
            project_name (str): Name of the project
            result (dict): Result dictionary to update
        """
        main_path = os.path.join(project_path, 'main.py')
        with open(main_path, 'w') as f:
            f.write(f'''#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Main script for {project_name}
"""

import sys
from {project_name}.core import hello

def main():
    """
    Main entry point for the application.
    """
    print(hello())
    return 0

if __name__ == "__main__":
    sys.exit(main())
''')
        result["files_created"].append(main_path)
    
    def _create_virtual_environment(self, project_path, result):
        """
        Create a virtual environment for the project
        
        Args:
            project_path (str): Path to the project
            result (dict): Result dictionary to update
            
        Returns:
            dict: Result of virtual environment creation
        """
        try:
            # Create venv directory
            venv_path = os.path.join(project_path, 'venv')
            
            # Try to create virtual environment
            subprocess.run(
                [sys.executable, "-m", "venv", venv_path],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            result["files_created"].append(venv_path)
            return {"success": True}
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to create virtual environment: {str(e)}"
            }
    
    def _is_pip_installed(self):
        """
        Check if pip is installed
        
        Returns:
            bool: True if pip is installed, False otherwise
        """
        try:
            subprocess.run(
                ["pip", "--version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False
            )
            return True
        except FileNotFoundError:
            return False 