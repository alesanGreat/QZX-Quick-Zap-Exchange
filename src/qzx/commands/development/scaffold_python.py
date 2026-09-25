"""Create a runnable, installable Python starter with optional tests."""

from ._scaffold_result_schema import starter_result_schema
from qzx.core.command_base import CommandBase
from ._python_scaffold_project import create_python_project


class ScaffoldPythonCommand(CommandBase):
    """
    Command to generate a basic scaffolding for a Python program.
    Creates a new Python project with standard directory structure and basic files.
    """
    
    name = "scaffoldPython"
    description = "Creates a basic scaffolding for a Python program"
    category = "development"
    result_schema = starter_result_schema(python=True)
    
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
            'default': True,
            'type': 'bool'
        },
        {
            'name': 'create_venv',
            'description': 'Whether to create a virtual environment',
            'required': False,
            'default': False,
            'type': 'bool'
        }
    ]
    
    examples = [
        {
            'command': 'qzx scaffoldPython my_project',
            'description': 'Creates a new Python project named "my_project" in the current directory'
        },
        {
            'command': 'qzx scaffoldPython my_project /path/to/dir true true',
            'description': 'Creates a new Python project with tests and virtual environment in the specified directory'
        },
        {
            'command': 'qzx scaffoldPython api_service . false',
            'description': 'Creates a new Python project named "api_service" without tests in the current directory'
        }
    ]
    
    def execute(self, project_name, path=".", with_tests=True, create_venv=False):
        """Generate files and actionable next steps, without implicit installation."""
        return create_python_project(project_name, path, with_tests, create_venv)
