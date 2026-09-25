"""The generated README is an executable onboarding path, not generic boilerplate."""

from string import Template

_INTRO = '''# $title

A small Python application. Replace this introduction with the problem it solves.

## First result: no installation required

Requires Python 3.11 or newer. Open a terminal in this project directory and run:

```console
python -m $name
```

Expected output: `Hello, world from $name!`

`python main.py` starts the same application. Neither command installs
dependencies or contacts a service. Edit `$name/core.py` to begin.

## Use from Python

```python
from $name import add, hello

print(hello())
assert add(2, 3) == 5
```

## Optional installation

The starter has no runtime dependencies. Installation makes its command
available outside this directory, using the Python environment you select:

```console
python -m pip install -e .
$name
```

Use `python -m pip`, not a possibly unrelated `pip` executable.
On an externally managed Python, use your existing development environment or
create a virtual environment instead of overriding the operating system's protection.

## Optional virtual environment

QZX creates no environment unless you explicitly request `create_venv=true`.
To create one yourself:

```console
python -m venv venv
```

Activation is optional. These commands use it directly without changing shell settings:

| Shell / system | Run the application | Install the optional project dependencies |
| --- | --- | --- |
| Windows CMD or PowerShell | `.\\venv\\Scripts\\python.exe -m $name` | `.\\venv\\Scripts\\python.exe -m pip install -e "$install_target"` |
| Linux or macOS | `./venv/bin/python -m $name` | `./venv/bin/python -m pip install -e "$install_target"` |

Creating a virtual environment does not install this project's development tools.
If QZX reports a failed environment attempt, the source files remain available;
fix the reported cause and complete the environment setup separately.
'''

_WITH_TESTS = '''
## Run the tests

Install the optional development dependencies in the environment you selected:

```console
python -m pip install -e ".[dev]"
python -m pytest
```

The test runner is optional; it is not needed for the first result.
Use the virtual environment's Python path above instead of `python` when applicable.
Tests live in `tests/test_core.py`; project metadata and test settings live in
`pyproject.toml`, so there is no second dependency list to keep synchronized.
'''

_WITHOUT_TESTS = '''
## Tests were not requested

This starter has no test directory, test-runner dependency or development extra.
Add a test suite when you need one; running the application needs no test tooling.
'''

_FINISH = '''
## Build a wheel when ready

```console
python -m pip wheel --no-deps . --wheel-dir dist
```

This explicit build may download the declared build backend. Review the wheel
in `dist/` before distributing it. Only your named application package is
included; tests and unrelated top-level packages are not application packages.

Before publishing, choose a unique distribution name, describe your application,
and set your own authors, license and project URLs in `pyproject.toml`.
No publishing account, ownership or license choice is invented for you.

## About the generator

Generated with [QZX — Quick Zap Exchange](https://qzx.yumbale.com/en/).
QZX — Quick Zap Exchange, created and maintained by Alejandro Sánchez.

This identifies the generator's creator, not the author of your application.
You can edit or remove this section. The generated application does not depend
on QZX. [Support QZX](https://qzx.yumbale.com/en/donate) or
[discuss an integration with Alejandro](https://qzx.yumbale.com/en/professional-services).
'''


def python_project_readme(name: str, with_tests: bool) -> str:
    """Keep every instruction consistent with the generated options."""
    content = _INTRO + (_WITH_TESTS if with_tests else _WITHOUT_TESTS) + _FINISH
    return Template(content).substitute(
        name=name,
        title=name.replace("_", " ").title(),
        install_target=".[dev]" if with_tests else ".",
    )
