# Python starter: create, run, test and package

> **Unreleased development workflow.** This guide describes the upgraded
> `scaffoldPython` in the development checkout. QZX 0.2.2.0.9 on PyPI predates
> this upgrade. Installing that release does not provide the layout or
> `next_steps` described here. The next coordinated release must update this
> notice together with its package, command examples and website.

Create a small Python application that runs before you install anything.
Then add tests, an installed command and a wheel when you need them.

## First useful result

Use the development checkout's QZX entry point in a parent directory where
you want to create a new project. Standard CPython 3.11 or later is required.

```console
qzx scaffoldPython my_app
cd my_app
python -m my_app
```

Expected output:

```text
Hello, world from my_app!
```

The generated `main.py` is also runnable with `python main.py`.
Neither the application nor this first run requires QZX, pytest or another
runtime dependency. Scaffolding does not install packages, contact a service,
create a Git repository, or select a license for your application.

Creation returns the actual normalized `project_name` and `project_path`.
For example, `My First-App` becomes `my_first_app`, `class` becomes
`py_class`, and `os` becomes `py_os`. Use the returned name when running or
importing your project. Keywords, standard-library names, scaffold directories
and reserved Windows device names are kept out of the package namespace.
Invalid names or ambiguous boolean options fail before project creation.

## Understand and change the generated code

| File | What to change |
| --- | --- |
| `my_app/core.py` | Your application logic; starts with `hello()` and `add()` |
| `my_app/__init__.py` | The package's public Python interface |
| `my_app/cli.py` | What your command prints and its exit status |
| `my_app/__main__.py` | The `python -m my_app` entry point |
| `pyproject.toml` | Dependencies, packaging and the installed command |
| `tests/test_core.py` | Two executable example tests, unless tests were disabled |
| `README.md` | Commands, expected output and environment-specific instructions |

From the project directory:

```python
from my_app import add, hello

print(hello())
assert add(2, 3) == 5
```

## Install and test only when needed

Choose the Python environment into which you intend to install the project.
Do not override an operating system's externally-managed-environment safeguard.

```console
python -m pip install -e ".[dev]"
python -m pytest
my_app
```

`pytest` is an optional development dependency, not an application runtime
dependency. The testless variant omits the test directory and development extra:

```console
qzx scaffoldPython lean_app --with-tests false
```

For that variant, optional editable installation is `python -m pip install -e .`.

An environment is optional, never created implicitly:

```console
qzx scaffoldPython isolated_app --create-venv true
```

The result distinguishes `not_requested`, `created` and `failed`. A failure to
create the requested environment preserves usable source files and returns an
explicit warning; it never reports an environment as created when it is not.
Use `venv/Scripts/python.exe` on Windows or `venv/bin/python` on Unix-like
systems, from inside the generated project, for subsequent Python commands.
The generated README includes shell-ready forms without requiring activation.

## Build an installable artifact

```console
python -m pip wheel --no-deps . --wheel-dir dist
```

This creates a wheel locally, not a PyPI publication. Build tools may be
downloaded by pip. Package discovery is limited to your application's package
and its subpackages, rather than silently packaging unrelated top-level folders.

Before publishing your application, choose its own distribution name, version,
description, authors, URLs and license. QZX does not claim Alejandro Sánchez as
the author of your application or assign it a fabricated repository URL.

## Use it from an agent

```console
qzx scaffoldPython my_app --json
```

The JSON result keeps `success`, `message`, created paths and the actual name.
It also exposes `virtual_environment`, `warnings`, and `next_steps`. Each next
step separates its argument array from its working directory:

```json
{
  "id": "run",
  "description": "Run the application without installing anything",
  "cwd": "<returned project_path>",
  "argv": ["<selected Python executable>", "-m", "my_app"]
}
```

This is a **schema illustration**, not a captured result. Treat the values in
your actual result as authoritative. Execute `argv` without a shell and with
the returned `cwd`. Installation, testing and building are suggestions, not
actions that QZX already performed. Obtain approval under your agent's policy
before performing suggested actions.

An existing target is refused, not merged or overwritten. On interrupted
creation, a failure result preserves `project_path`, `files_created` and
`partial: true` when paths were already created. Inspect that inventory before
retrying; do not delete unrelated content.

## Verification and limitations

The development tests execute the generated README snippet, module and direct
script, run the generated pytest suite, create a real optional environment,
and build and install a real wheel outside the source project. They also
exercise reserved names, rejected options, existing files, partial creation
and the no-process/no-network default. See
`tests/test_development_commands/test_scaffold_python_workflow.py`.

The campaign first verified Windows with standard CPython 3.13. A successful
Windows run is not evidence of every operating system or Python version.
These focused checks do not replace QZX's full architecture, regression,
documentation and release gates.

## About the generator

QZX — Quick Zap Exchange, created and maintained by Alejandro Sánchez.

The generated README's optional generator credit links to
[QZX](https://qzx.yumbale.com/en/),
[voluntary support](https://qzx.yumbale.com/en/donate), and
[professional services](https://qzx.yumbale.com/en/professional-services).
It credits the generator, not your application; you may edit or remove it.
QZX Core remains free and open source.

Packaging conventions follow the
[Python Packaging User Guide](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/).
