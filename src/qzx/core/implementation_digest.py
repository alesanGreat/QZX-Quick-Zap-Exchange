#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Canonical source fingerprinting for QZX public command implementations."""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
from functools import lru_cache
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SOURCE_ROOT = PROJECT_ROOT / "src"
COMMAND_LIFECYCLE_SOURCE_PATH = "src/qzx/resources/command-lifecycle.json"
SHARED_COMMAND_RUNTIME_MODULES = (
    "qzx.__main__",
    "qzx.cli",
    "qzx.core.command_base",
    "qzx.core.command_lifecycle",
    "qzx.core.command_loader",
)
NON_BEHAVIORAL_GENERATED_SOURCE_PATHS = frozenset(
    {
        # Release metadata changes between candidates without changing one
        # command's implementation or safety behavior.
        "src/qzx/_build_info.py",
    }
)


@lru_cache(maxsize=None)
def local_module_path(module_name: str) -> Path | None:
    """Resolve one local QZX module without importing it."""

    if not module_name or not module_name.startswith("qzx"):
        return None
    module_path = SOURCE_ROOT.joinpath(*module_name.split("."))
    file_candidate = module_path.with_suffix(".py")
    if file_candidate.is_file():
        return file_candidate
    package_candidate = module_path / "__init__.py"
    if package_candidate.is_file():
        return package_candidate
    return None


@lru_cache(maxsize=None)
def imported_local_modules(path: Path, module_name: str) -> frozenset[str]:
    """Return statically declared local imports for one Python source file."""

    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    imported: set[str] = set()
    package_name = (
        module_name
        if path.name == "__init__.py"
        else module_name.rpartition(".")[0]
    )

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(
                alias.name
                for alias in node.names
                if alias.name.startswith("qzx")
            )
            continue
        if not isinstance(node, ast.ImportFrom):
            continue

        if node.level:
            relative_name = "." * node.level + (node.module or "")
            try:
                resolved = importlib.util.resolve_name(relative_name, package_name)
            except (ImportError, ValueError):
                continue
        else:
            resolved = node.module or ""

        if not resolved.startswith("qzx"):
            continue
        imported.add(resolved)
        for alias in node.names:
            if alias.name != "*":
                imported.add("{}.{}".format(resolved, alias.name))

    return frozenset(imported)


@lru_cache(maxsize=None)
def implementation_source_paths(cmd_class: type[Any]) -> tuple[str, ...]:
    """Return transitive maintained sources that define one public command."""

    pending = set(SHARED_COMMAND_RUNTIME_MODULES)
    pending.add(cmd_class.__module__)
    visited_modules: set[str] = set()
    source_paths = {COMMAND_LIFECYCLE_SOURCE_PATH}

    while pending:
        module_name = pending.pop()
        if module_name in visited_modules:
            continue
        visited_modules.add(module_name)
        parts = module_name.split(".")
        pending.update(
            ".".join(parts[:index])
            for index in range(1, len(parts))
            if ".".join(parts[:index]) not in visited_modules
        )
        path = local_module_path(module_name)
        if path is None:
            continue
        relative_path = path.relative_to(PROJECT_ROOT).as_posix()
        if relative_path not in NON_BEHAVIORAL_GENERATED_SOURCE_PATHS:
            source_paths.add(relative_path)
        pending.update(imported_local_modules(path, module_name) - visited_modules)

    return tuple(sorted(source_paths))


def canonicalize_source_bytes(raw: bytes) -> bytes:
    """Normalize UTF-8 text so fingerprints are independent of checkout EOLs."""

    text = raw.decode("utf-8-sig")
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


@lru_cache(maxsize=None)
def source_bytes(relative_path: str) -> bytes:
    """Read source text once and normalize it to portable UTF-8/LF bytes."""

    return canonicalize_source_bytes((PROJECT_ROOT / relative_path).read_bytes())


@lru_cache(maxsize=1)
def load_lifecycle_digest_document() -> dict[str, Any]:
    """Load lifecycle metadata for semantic per-command digest projection."""

    return json.loads(
        source_bytes(COMMAND_LIFECYCLE_SOURCE_PATH).decode("utf-8-sig")
    )


def command_lifecycle_digest_projection(
    cmd_class: type[Any],
    lifecycle_document: dict[str, Any],
) -> dict[str, Any]:
    """Project only lifecycle facts that can affect one command's behavior."""

    command_entry = lifecycle_document["commands"][cmd_class.name]
    stage_name = command_entry["stage"]
    return {
        "schema_version": lifecycle_document["schema_version"],
        "assessment_scope": lifecycle_document["assessment"]["scope"],
        "command": command_entry,
        "stage_name": stage_name,
        "stage": lifecycle_document["stages"][stage_name],
    }


def command_implementation_digest_for_lifecycle(
    cmd_class: type[Any],
    lifecycle_document: dict[str, Any],
) -> str:
    """Hash implementation sources with a command-scoped lifecycle projection."""

    digest = hashlib.sha256()
    for relative_path in implementation_source_paths(cmd_class):
        if relative_path == COMMAND_LIFECYCLE_SOURCE_PATH:
            continue
        digest.update(relative_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(source_bytes(relative_path))
        digest.update(b"\0")

    projection_path = "{}#{}".format(
        COMMAND_LIFECYCLE_SOURCE_PATH,
        cmd_class.name,
    )
    projection_bytes = json.dumps(
        command_lifecycle_digest_projection(cmd_class, lifecycle_document),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    digest.update(projection_path.encode("utf-8"))
    digest.update(b"\0")
    digest.update(projection_bytes)
    digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def command_implementation_digest(cmd_class: type[Any]) -> str:
    """Fingerprint one command, its runtime, and its lifecycle metadata."""

    return command_implementation_digest_for_lifecycle(
        cmd_class,
        load_lifecycle_digest_document(),
    )
