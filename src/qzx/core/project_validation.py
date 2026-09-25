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
    return {
        "execution_policy": "discovery_only",
        "execution_note": (
            "diagnoseProject never executes project-owned tests, linters, type "
            "checkers, builds, package scripts, hooks, or installers."
        ),
        "tests": _inspect_test_workflows(
            project_root, root_names, technologies, tool_config,
            package_scripts, package_dependencies, composer_dev,
        ),
        "lint": _inspect_lint_workflows(root_names, tool_config, package_scripts),
        "type_checking": _inspect_type_workflows(
            root_names, tool_config, package_scripts,
        ),
        "build": _inspect_build_workflows(
            root_names, technologies, pyproject, package_scripts,
        ),
    }


def _inspect_test_workflows(
    project_root, root_names, technologies, tool_config,
    package_scripts, package_dependencies, composer_dev,
):
    record = _validation_record()
    directories = [
        name for name in ("tests", "test", "spec") if (project_root / name).is_dir()
    ]
    record["configs"].extend(directories)
    has_pytest = (
        "Python" in technologies
        and (directories or "pytest.ini" in root_names or isinstance(tool_config.get("pytest"), dict))
    )
    if has_pytest:
        record["tools"].append("pytest")
        record["commands"].append("python -m pytest")
        if isinstance(tool_config.get("pytest"), dict):
            record["configs"].append("pyproject.toml [tool.pytest]")
    if "test" in package_scripts:
        record["tools"].append(_detect_node_test_tool(package_dependencies))
        record["commands"].append(_package_manager_command(root_names, "test"))
        record["configs"].append("package.json [scripts.test]")
    if "phpunit/phpunit" in composer_dev or {"phpunit.xml", "phpunit.xml.dist"} & root_names:
        record["tools"].append("phpunit")
        record["commands"].append("vendor/bin/phpunit")
    for technology, tool, command in (
        ("Rust", "cargo test", "cargo test"),
        ("Go", "go test", "go test ./..."),
    ):
        if technology in technologies:
            record["tools"].append(tool)
            record["commands"].append(command)
    return _finalized_validation_record(record)


def _inspect_lint_workflows(root_names, tool_config, package_scripts):
    record = _validation_record()
    for section in ("ruff", "black", "isort", "flake8", "pylint"):
        if section in tool_config:
            record["tools"].append(section)
            record["configs"].append(f"pyproject.toml [tool.{section}]")
    if "ruff" in record["tools"]:
        record["commands"].append("python -m ruff check .")
    if "lint" in package_scripts:
        record["tools"].append("package script")
        record["commands"].append(_package_manager_command(root_names, "lint"))
        record["configs"].append("package.json [scripts.lint]")
    eslint_configs = [
        name for name in root_names
        if name.startswith(".eslintrc") or name.startswith("eslint.config.")
    ]
    if eslint_configs:
        record["tools"].append("ESLint")
        record["configs"].extend(eslint_configs)
    return _finalized_validation_record(record)


def _inspect_type_workflows(root_names, tool_config, package_scripts):
    record = _validation_record()
    if "mypy" in tool_config:
        record["tools"].append("mypy")
        record["configs"].append("pyproject.toml [tool.mypy]")
        record["commands"].append("python -m mypy .")
    if "pyright" in tool_config or "pyrightconfig.json" in root_names:
        record["tools"].append("pyright")
        record["configs"].append(
            "pyproject.toml [tool.pyright]" if "pyright" in tool_config else "pyrightconfig.json"
        )
        record["commands"].append("pyright")
    if "tsconfig.json" in root_names:
        record["tools"].append("TypeScript")
        record["configs"].append("tsconfig.json")
        record["commands"].append("npx tsc --noEmit")
    if "typecheck" in package_scripts:
        record["tools"].append("package script")
        record["configs"].append("package.json [scripts.typecheck]")
        record["commands"].append(_package_manager_command(root_names, "typecheck"))
    return _finalized_validation_record(record)


def _inspect_build_workflows(root_names, technologies, pyproject, package_scripts):
    record = _validation_record()
    pyproject_build = isinstance(pyproject, dict) and isinstance(pyproject.get("build-system"), dict)
    if "Python" in technologies and ("setup.py" in root_names or pyproject_build):
        record["tools"].append("PEP 517")
        record["configs"].append("pyproject.toml [build-system]" if pyproject_build else "setup.py")
        record["commands"].append("python -m build")
    if "build" in package_scripts:
        record["tools"].append("package script")
        record["configs"].append("package.json [scripts.build]")
        record["commands"].append(_package_manager_command(root_names, "build"))
    for technology, tool, command in (
        ("Rust", "cargo", "cargo build"),
        ("Go", "go", "go build ./..."),
    ):
        if technology in technologies:
            record["tools"].append(tool)
            record["commands"].append(command)
    return _finalized_validation_record(record)


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


def _finalized_validation_record(record: dict[str, object]) -> dict[str, object]:
    _finalize_validation_record(record)
    return record


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
