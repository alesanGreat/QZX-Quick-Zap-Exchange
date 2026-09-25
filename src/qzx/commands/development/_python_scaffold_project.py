"""Validate, create and report a Python project without implicit installation."""

import keyword
import os
from pathlib import Path
import subprocess
import sys
import unicodedata

from ._scaffold_utils import (
    normalize_project_name,
    parse_scaffold_boolean,
    prepare_scaffold_project,
)
from ._python_scaffold_readme import python_project_readme
from ._python_scaffold_templates import python_project_files

_RESERVED = {
    "tests", "build", "dist", "venv", "env", "main", "qzx",
    "pip", "pytest", "setuptools", "wheel",
    "con", "prn", "aux", "nul",
    *(f"com{number}" for number in range(1, 10)),
    *(f"lpt{number}" for number in range(1, 10)),
}


def python_project_name(value: str) -> str:
    """Produce an importable, portable distribution name before any writes."""
    if not isinstance(value, str):
        raise ValueError("project_name must be text, for example my_app.")
    normalized = unicodedata.normalize("NFKC", value)
    if not normalized.isascii():
        raise ValueError("Use an ASCII project name, for example cafe_app.")
    name = normalize_project_name(normalized, leading_prefix="py_").strip("_")
    if not name or not name.isidentifier():
        raise ValueError("Use a project name containing letters or digits.")
    if keyword.iskeyword(name) or name in _RESERVED or name in sys.stdlib_module_names:
        name = "py_" + name
    return name


def _write_project(result: dict, contents: dict[str, str]) -> None:
    """Record created paths and never overwrite a file that appeared concurrently."""
    root = Path(result["project_path"])
    for relative, content in contents.items():
        target = root / relative
        if target.parent != root and not target.parent.exists():
            target.parent.mkdir()
            result["files_created"].append(str(target.parent))
        with target.open("x", encoding="utf-8", newline="\n") as stream:
            result["files_created"].append(str(target))
            stream.write(content)


def _create_environment(root: Path) -> dict:
    """An optional failed environment does not invalidate usable source files."""
    path = root / "venv"
    python = path / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    state = {"requested": True, "status": "failed", "path": str(path)}
    print("Creating the requested virtual environment; no project dependencies "
          "will be installed.", file=sys.stderr, flush=True)
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "venv", str(path)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            check=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if completed.returncode:
            state["message"] = (
                f"Virtual environment creation exited with {completed.returncode}: "
                + (completed.stderr.strip() or completed.stdout.strip())[-2000:]
            )
        elif not python.is_file() or not (path / "pyvenv.cfg").is_file():
            state["message"] = "The environment command did not create a usable Python layout."
        else:
            state.update(status="created", python=str(python),
                         message="Virtual environment created; project dependencies not installed.")
    except OSError as error:
        state["message"] = f"Virtual environment creation could not start: {error}"
    return state


def _next_steps(result: dict) -> list[dict]:
    """Return argv and cwd separately so agents need no shell-string parsing."""
    interpreter = result["virtual_environment"].get("python", sys.executable)
    steps = [
        ("run", "Run the application without installing anything",
         ["-m", result["project_name"]]),
        ("install", "Optionally install into your selected Python environment",
         ["-m", "pip", "install", "-e", ".[dev]" if result["with_tests"] else "."]),
    ]
    if result["with_tests"]:
        steps.append(("test", "Run tests after installing the development extra",
                      ["-m", "pytest"]))
    steps.append(("build", "Optionally build a wheel; build tools may be downloaded",
                  ["-m", "pip", "wheel", "--no-deps", ".", "--wheel-dir", "dist"]))
    return [
        {"id": key, "description": description, "cwd": result["project_path"],
         "argv": [interpreter, *arguments]}
        for key, description, arguments in steps
    ]


def _complete_result(result: dict) -> dict:
    """Separate requested work, completed work and suggested future actions."""
    root = Path(result["project_path"])
    environment = result["virtual_environment"]
    if environment["status"] == "created":
        result["files_created"].append(environment["path"])
    result["warnings"] = (
        [environment["message"]] if environment["status"] == "failed" else []
    )
    result["next_steps"] = _next_steps(result)
    result["message"] = (
        f"Created Python project '{result['project_name']}' with "
        f"{'tests' if result['with_tests'] else 'no tests'} at {root}. "
        "Run it immediately; no project dependencies were installed."
    )
    report = [
        result["message"], "", "From the project directory:",
        f"  python -m {result['project_name']}",
        "", "Expected: Hello, world from " + result["project_name"] + "!",
        "See README.md for installation, tests and wheel packaging.",
        "Virtual environment: " + environment["status"].replace("_", " ") + ".",
    ]
    if result["warnings"]:
        result["message"] += " The optional virtual environment failed; see warnings."
        report.extend(["", "Warning: " + environment["message"],
                       "Source files were kept; review the environment path before retrying."])
    result["report"] = "\n".join(report)
    return result


def _failed_result(name, error: Exception, partial: dict | None) -> dict:
    """Keep recovery evidence instead of concealing an interrupted creation."""
    result = {
        "success": False, "error_code": "scaffold_failed", "error": str(error),
        "message": f"Could not create Python project: {error}",
        "project_name": name,
    }
    if partial is not None:
        result.update(project_path=partial["project_path"],
                      files_created=partial["files_created"], partial=True)
        result["message"] += " Created paths were preserved; inspect them before retrying."
    return result


def create_python_project(project_name, path=".", with_tests=True, create_venv=False):
    """Build a runnable starter, preserving options and partial failure evidence."""
    result = None
    try:
        with_tests = parse_scaffold_boolean(with_tests, "with_tests")
        create_venv = parse_scaffold_boolean(create_venv, "create_venv")
        name = python_project_name(project_name)
        contents = python_project_files(name, with_tests)
        contents["README.md"] = python_project_readme(name, with_tests)
        result = prepare_scaffold_project(
            name, os.path.abspath(os.fspath(path)),
            {"with_tests": with_tests, "create_venv": create_venv},
        )
        if not result["success"]:
            return result
        result["requested_project_name"] = project_name
        result["name_was_normalized"] = name != project_name
        _write_project(result, contents)
        result["virtual_environment"] = (
            _create_environment(Path(result["project_path"])) if create_venv else
            {"requested": False, "status": "not_requested"}
        )
        return _complete_result(result)
    except Exception as error:
        return _failed_result(project_name, error, result)
