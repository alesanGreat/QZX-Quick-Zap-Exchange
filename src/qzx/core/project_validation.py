"""Discover project validation workflows without executing project code."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def inspect_validation_workflows(
    project_root: Path,
    root_names: set[str],
    technologies: list[str],
    pyproject: Any,
    package_json: Any,
    composer_json: Any,
) -> dict[str, object]:
    """Return configured test, lint, type-check, and build workflows."""
    tool_config = _mapping_section(pyproject, "tool")
    package_scripts = _mapping_section(package_json, "scripts")
    package_dependencies = _mapping_values(
        package_json,
        ("dependencies", "devDependencies"),
    )
    composer_dev = _mapping_section(composer_json, "require-dev")

    tests = _validation_record()
    test_directories = [
        name for name in ("tests", "test", "spec") if (project_root / name).is_dir()
    ]
    if test_directories:
        tests["configs"].extend(test_directories)
    if "Python" in technologies and (
        test_directories
        or "pytest.ini" in root_names
        or isinstance(tool_config.get("pytest"), dict)
    ):
        tests["tools"].append("pytest")
        tests["commands"].append("python -m pytest")
        if isinstance(tool_config.get("pytest"), dict):
            tests["configs"].append("pyproject.toml [tool.pytest]")
    if "test" in package_scripts:
        tests["tools"].append(_detect_node_test_tool(package_dependencies))
        tests["commands"].append(_package_manager_command(root_names, "test"))
        tests["configs"].append("package.json [scripts.test]")
    if "phpunit/phpunit" in composer_dev or {
        "phpunit.xml",
        "phpunit.xml.dist",
    } & root_names:
        tests["tools"].append("phpunit")
        tests["commands"].append("vendor/bin/phpunit")
    if "Rust" in technologies:
        tests["tools"].append("cargo test")
        tests["commands"].append("cargo test")
    if "Go" in technologies:
        tests["tools"].append("go test")
        tests["commands"].append("go test ./...")
    _finalize_validation_record(tests)

    lint = _validation_record()
    python_linters = {
        "ruff": "ruff",
        "black": "black",
        "isort": "isort",
        "flake8": "flake8",
        "pylint": "pylint",
    }
    for section, label in python_linters.items():
        if section in tool_config:
            lint["tools"].append(label)
            lint["configs"].append(f"pyproject.toml [tool.{section}]")
    if "ruff" in lint["tools"]:
        lint["commands"].append("python -m ruff check .")
    if "lint" in package_scripts:
        lint["tools"].append("package script")
        lint["commands"].append(_package_manager_command(root_names, "lint"))
        lint["configs"].append("package.json [scripts.lint]")
    eslint_configs = [
        name
        for name in root_names
        if name.startswith(".eslintrc") or name.startswith("eslint.config.")
    ]
    if eslint_configs:
        lint["tools"].append("ESLint")
        lint["configs"].extend(eslint_configs)
    _finalize_validation_record(lint)

    type_checking = _validation_record()
    if "mypy" in tool_config:
        type_checking["tools"].append("mypy")
        type_checking["configs"].append("pyproject.toml [tool.mypy]")
        type_checking["commands"].append("python -m mypy .")
    if "pyright" in tool_config or "pyrightconfig.json" in root_names:
        type_checking["tools"].append("pyright")
        type_checking["configs"].append(
            "pyproject.toml [tool.pyright]"
            if "pyright" in tool_config
            else "pyrightconfig.json"
        )
        type_checking["commands"].append("pyright")
    if "tsconfig.json" in root_names:
        type_checking["tools"].append("TypeScript")
        type_checking["configs"].append("tsconfig.json")
        type_checking["commands"].append("npx tsc --noEmit")
    if "typecheck" in package_scripts:
        type_checking["tools"].append("package script")
        type_checking["configs"].append("package.json [scripts.typecheck]")
        type_checking["commands"].append(
            _package_manager_command(root_names, "typecheck")
        )
    _finalize_validation_record(type_checking)

    build = _validation_record()
    if "Python" in technologies and (
        "setup.py" in root_names
        or isinstance(pyproject, dict)
        and isinstance(pyproject.get("build-system"), dict)
    ):
        build["tools"].append("PEP 517")
        build["configs"].append(
            "pyproject.toml [build-system]"
            if isinstance(pyproject, dict)
            and isinstance(pyproject.get("build-system"), dict)
            else "setup.py"
        )
        build["commands"].append("python -m build")
    if "build" in package_scripts:
        build["tools"].append("package script")
        build["configs"].append("package.json [scripts.build]")
        build["commands"].append(_package_manager_command(root_names, "build"))
    if "Rust" in technologies:
        build["tools"].append("cargo")
        build["commands"].append("cargo build")
    if "Go" in technologies:
        build["tools"].append("go")
        build["commands"].append("go build ./...")
    _finalize_validation_record(build)

    return {
        "execution_policy": "discovery_only",
        "execution_note": (
            "diagnoseProject never executes project-owned tests, linters, type "
            "checkers, builds, package scripts, hooks, or installers."
        ),
        "tests": tests,
        "lint": lint,
        "type_checking": type_checking,
        "build": build,
    }


def _mapping_values(document: Any, keys: tuple[str, ...]) -> dict[str, object]:
    values: dict[str, object] = {}
    if not isinstance(document, dict):
        return values
    for key in keys:
        group = document.get(key, {})
        if isinstance(group, dict):
            values.update(group)
    return values


def _mapping_section(document: Any, key: str) -> dict[str, object]:
    if not isinstance(document, dict) or "_qzx_parse_error" in document:
        return {}
    value = document.get(key, {})
    return value if isinstance(value, dict) else {}


def _validation_record() -> dict[str, object]:
    return {
        "configured": False,
        "status": "not_configured",
        "tools": [],
        "configs": [],
        "commands": [],
    }


def _finalize_validation_record(record: dict[str, object]) -> None:
    for key in ("tools", "configs", "commands"):
        record[key] = list(dict.fromkeys(record[key]))
    record["configured"] = bool(record["tools"] or record["commands"])
    record["status"] = (
        "configured_not_run" if record["configured"] else "not_configured"
    )


def _detect_node_test_tool(dependencies: dict[str, object]) -> str:
    names = {name.casefold() for name in dependencies}
    if "vitest" in names:
        return "Vitest"
    if "jest" in names:
        return "Jest"
    if "mocha" in names:
        return "Mocha"
    return "package test script"


def _package_manager_command(root_names: set[str], script: str) -> str:
    if "pnpm-lock.yaml" in root_names:
        return f"pnpm run {script}"
    if "yarn.lock" in root_names:
        return f"yarn {script}"
    if "bun.lock" in root_names or "bun.lockb" in root_names:
        return f"bun run {script}"
    return f"npm run {script}"
