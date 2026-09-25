"""Guardrails against mechanical refactors that only move God Code around."""

from __future__ import annotations

import ast
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
COMMAND_ROOT = PROJECT_ROOT / "src" / "qzx" / "commands"
SOURCE_ROOTS = ("src", "scripts", "tests")
NUMBERED_SPLIT = re.compile(r"_part\d+\.py\Z", re.IGNORECASE)


def test_numbered_split_modules_are_not_committed():
    """Require semantic module names instead of *_part2.py-style slicing."""
    violations = []

    for root_name in SOURCE_ROOTS:
        root = PROJECT_ROOT / root_name
        if not root.exists():
            continue
        for source in root.rglob("*.py"):
            if NUMBERED_SPLIT.search(source.name):
                violations.append(source.relative_to(PROJECT_ROOT).as_posix())

    assert violations == [], (
        "Mechanical numbered split modules hide architecture instead of naming "
        "responsibilities. Use semantic module names:\n" + "\n".join(violations)
    )


def test_private_command_helpers_are_referenced_by_imports():
    """Do not leave extracted helper modules orphaned after a rollback or restore."""
    imported_modules = set()
    helpers = []

    for source in COMMAND_ROOT.rglob("*.py"):
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module:
                    imported_modules.add(node.module.rsplit(".", 1)[-1])
                imported_modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.Import):
                imported_modules.update(
                    alias.name.rsplit(".", 1)[-1] for alias in node.names
                )
        if source.name.startswith("_") and source.name != "__init__.py":
            helpers.append(source)

    orphans = [
        source.relative_to(COMMAND_ROOT).as_posix()
        for source in helpers
        if source.stem not in imported_modules
    ]

    assert orphans == [], (
        "Private command helpers must be referenced by an import; orphan helpers "
        "usually indicate a partial mechanical refactor or rollback:\n"
        + "\n".join(orphans)
    )
