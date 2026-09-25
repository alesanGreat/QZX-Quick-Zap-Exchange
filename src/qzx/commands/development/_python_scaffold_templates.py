"""Small source templates for the runnable Python starter (no runtime dependencies)."""

from string import Template

_PACKAGE = '''"""$name: replace this description with your project's purpose."""
from .core import add, hello

__version__ = "0.1.0"
__all__ = ["add", "hello"]
'''

_CORE = '''"""Core functionality for $name."""


def hello() -> str:
    """Return a greeting to verify the first run."""
    return "Hello, world from $name!"


def add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b
'''

_CLI = '''"""Command-line entry point for $name."""
from .core import hello


def main() -> int:
    """Print a greeting and return a successful process status."""
    print(hello())
    return 0
'''

_MODULE = '''"""Run with python -m $name."""
from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
'''

_MAIN = '''"""Run the same entry point directly with python main.py."""
from $name.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
'''

_TESTS = '''"""Tests for $name.core and its public package API."""
from $name import add, hello


def test_hello():
    assert hello() == "Hello, world from $name!"


def test_add():
    assert add(1, 2) == 3
    assert add(5, 7) == 12
    assert add(-1, 1) == 0
    assert add(0, 0) == 0
'''

_PYPROJECT = '''[build-system]
requires = ["setuptools>=77.0.3"]
build-backend = "setuptools.build_meta"

[project]
name = "$name"
version = "0.1.0"
description = "A Python application"
readme = "README.md"
requires-python = ">=3.11"
dependencies = []
# Add YOUR authors, project URLs and chosen license before publishing.
# QZX generates the scaffold; it is not the author of your application.

[project.scripts]
$name = "$name.cli:main"

[tool.setuptools.packages.find]
where = ["."]
include = ["$name", "$name.*"]
namespaces = false
'''

_TEST_CONFIG = '''
[project.optional-dependencies]
dev = ["pytest>=7"]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_functions = ["test_*"]
'''

_GITIGNORE = '''# Python bytecode and test output
__pycache__/
*.py[cod]
.pytest_cache/
.coverage
htmlcov/
# Build artifacts
build/
dist/
*.egg-info/
# Optional environments
.venv/
venv/
env/
ENV/
# Editors and operating systems
.idea/
.vscode/
*.swp
*.swo
.DS_Store
Thumbs.db
'''


def python_project_files(name: str, with_tests: bool) -> dict[str, str]:
    """Render a complete plan before writing any project content."""
    templates = {
        f"{name}/__init__.py": _PACKAGE,
        f"{name}/core.py": _CORE,
        f"{name}/cli.py": _CLI,
        f"{name}/__main__.py": _MODULE,
        "main.py": _MAIN,
        "pyproject.toml": _PYPROJECT + (_TEST_CONFIG if with_tests else ""),
        ".gitignore": _GITIGNORE,
        "MANIFEST.in": "include main.py\n",
    }
    if with_tests:
        templates["tests/test_core.py"] = _TESTS
    return {
        path: Template(content).substitute(name=name)
        for path, content in templates.items()
    }
