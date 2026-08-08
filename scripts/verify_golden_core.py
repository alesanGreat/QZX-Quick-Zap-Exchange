#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Validate the public QZX Golden Core candidate registry."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
GOLDEN_CORE_PATH = SOURCE_ROOT / "qzx" / "resources" / "golden-core.json"
COMMAND_INDEX_PATH = SOURCE_ROOT / "qzx" / "resources" / "command-index.json"
LIFECYCLE_PATH = SOURCE_ROOT / "qzx" / "resources" / "command-lifecycle.json"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from qzx.core.command_loader import CommandLoader  # noqa: E402


_ROLE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
_REQUIRED_DIMENSIONS = {
    "behavioral_tests",
    "policy_review",
    "success_evidence",
    "failure_evidence",
    "result_contract_review",
    "platform_evidence",
    "release_quality",
    "lifecycle_review",
}


def load_json(path: Path, label: str) -> dict[str, Any]:
    """Load one required JSON object."""

    with path.open("r", encoding="utf-8") as handle:
        document = json.load(handle)
    if not isinstance(document, dict):
        raise ValueError(f"{label} must contain a JSON object.")
    return document


def load_golden_core() -> dict[str, Any]:
    """Load the canonical packaged Golden Core registry."""

    return load_json(GOLDEN_CORE_PATH, "golden-core.json")


def _nonempty_text(value: Any) -> bool:
    return isinstance(value, str) and value.strip() != ""


def validate_golden_core(
    registry: dict[str, Any] | None = None,
    *,
    catalog_path: Path | None = None,
) -> list[str]:
    """Return deterministic validation errors for the Golden Core registry."""

    registry = registry if registry is not None else load_golden_core()
    command_index = load_json(COMMAND_INDEX_PATH, "command-index.json")
    lifecycle = load_json(LIFECYCLE_PATH, "command-lifecycle.json")
    errors: list[str] = []

    if registry.get("schema_version") != 1:
        errors.append("golden-core.json must use schema_version 1.")
    if registry.get("name") != "QZX Golden Core":
        errors.append("golden-core.json must identify QZX Golden Core.")
    if registry.get("status") != "candidate":
        errors.append("Golden Core must remain a candidate until separately reviewed.")
    if registry.get("target_maturity") != "beta":
        errors.append("Golden Core target_maturity must be beta.")
    for field in (
        "selected_on",
        "maintainer",
        "purpose",
        "purpose_es",
        "disclaimer",
        "disclaimer_es",
    ):
        if not _nonempty_text(registry.get(field)):
            errors.append(f"Golden Core {field} must be non-empty text.")

    principles = registry.get("selection_principles")
    if not isinstance(principles, list) or len(principles) < 4:
        errors.append("Golden Core must declare at least four selection principles.")
    else:
        for index, principle in enumerate(principles):
            if not isinstance(principle, dict) or any(
                not _nonempty_text(principle.get(locale))
                for locale in ("en", "es")
            ):
                errors.append(
                    f"selection_principles[{index}] must contain English "
                    "and Spanish text."
                )

    dimensions = registry.get("readiness_dimensions")
    dimension_ids: list[str] = []
    if not isinstance(dimensions, list):
        errors.append("Golden Core readiness_dimensions must be an array.")
    else:
        for index, item in enumerate(dimensions):
            if not isinstance(item, dict):
                errors.append(f"readiness_dimensions[{index}] must be an object.")
                continue
            dimension_id = item.get("id")
            description = item.get("description")
            description_es = item.get("description_es")
            if not isinstance(dimension_id, str) or _ROLE_PATTERN.fullmatch(dimension_id) is None:
                errors.append(
                    f"readiness_dimensions[{index}].id must use lower_snake_case."
                )
            else:
                dimension_ids.append(dimension_id)
            if not _nonempty_text(description):
                errors.append(
                    f"readiness_dimensions[{index}].description must be non-empty text."
                )
            if not _nonempty_text(description_es):
                errors.append(
                    f"readiness_dimensions[{index}].description_es must be non-empty text."
                )
        duplicates = sorted(
            item for item, count in Counter(dimension_ids).items() if count > 1
        )
        if duplicates:
            errors.append(
                "Golden Core readiness dimensions are duplicated: "
                + ", ".join(duplicates)
                + "."
            )
        missing_dimensions = sorted(_REQUIRED_DIMENSIONS - set(dimension_ids))
        extra_dimensions = sorted(set(dimension_ids) - _REQUIRED_DIMENSIONS)
        if missing_dimensions:
            errors.append(
                "Golden Core is missing readiness dimensions: "
                + ", ".join(missing_dimensions)
                + "."
            )
        if extra_dimensions:
            errors.append(
                "Golden Core has unknown readiness dimensions: "
                + ", ".join(extra_dimensions)
                + "."
            )

    indexed = command_index.get("commands")
    indexed_names = {
        item.get("name")
        for item in indexed
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    } if isinstance(indexed, list) else set()
    lifecycle_commands = lifecycle.get("commands")
    lifecycle_stages = lifecycle.get("stages")
    if not indexed_names:
        errors.append("The packaged command index has no commands.")
    if not isinstance(lifecycle_commands, dict) or not isinstance(lifecycle_stages, dict):
        errors.append("The packaged command lifecycle registry is incomplete.")
        lifecycle_commands = {}
        lifecycle_stages = {}

    commands = registry.get("commands")
    command_names: list[str] = []
    loader = CommandLoader()
    if not isinstance(commands, list) or not 10 <= len(commands) <= 20:
        errors.append("Golden Core must contain between 10 and 20 commands.")
        commands = []
    for index, item in enumerate(commands):
        context = f"commands[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{context} must be an object.")
            continue
        name = item.get("name")
        role = item.get("role")
        rationale = item.get("rationale")
        rationale_es = item.get("rationale_es")
        if not _nonempty_text(name):
            errors.append(f"{context}.name must be non-empty text.")
            continue
        command_names.append(name)
        if not isinstance(role, str) or _ROLE_PATTERN.fullmatch(role) is None:
            errors.append(f"{context}.role must use lower_snake_case.")
        if not _nonempty_text(rationale) or len(rationale.strip()) < 30:
            errors.append(f"{context}.rationale must explain the selection.")
        if not _nonempty_text(rationale_es) or len(rationale_es.strip()) < 30:
            errors.append(f"{context}.rationale_es must explain the selection.")
        if name not in indexed_names:
            errors.append(f"Golden Core command is absent from command-index.json: {name}.")
            continue
        lifecycle_entry = lifecycle_commands.get(name)
        if not isinstance(lifecycle_entry, dict):
            errors.append(f"Golden Core command has no lifecycle entry: {name}.")
        else:
            stage_name = lifecycle_entry.get("stage")
            stage = lifecycle_stages.get(stage_name)
            if not isinstance(stage, dict) or stage.get("public_executable") is not True:
                errors.append(f"Golden Core command is not publicly executable: {name}.")
        command = loader.get_command(name)
        if command is None:
            errors.append(f"Golden Core command could not be loaded: {name}.")
            continue
        if command.name != name:
            errors.append(f"Golden Core command does not use its canonical name: {name}.")
        if bool(getattr(command, "requires_explicit_approval", False)):
            errors.append(f"Golden Core command requires high-risk approval: {name}.")
        if getattr(command, "backup_target_parameter", None) is not None:
            errors.append(f"Golden Core command declares a mutation backup target: {name}.")

    duplicate_commands = sorted(
        name for name, count in Counter(command_names).items() if count > 1
    )
    if duplicate_commands:
        errors.append(
            "Golden Core commands are duplicated: "
            + ", ".join(duplicate_commands)
            + "."
        )

    if catalog_path is not None:
        catalog = load_json(catalog_path, "generated command catalog")
        catalog_commands = catalog.get("commands")
        if not isinstance(catalog_commands, dict):
            errors.append("The generated command catalog has no commands object.")
        else:
            for name in command_names:
                command = catalog_commands.get(name)
                if not isinstance(command, dict):
                    errors.append(f"Generated catalog is missing Golden Core command: {name}.")
                    continue
                safety = command.get("safety")
                availability = command.get("availability")
                if not isinstance(safety, dict) or safety.get("operation") != "read-only":
                    errors.append(f"Reviewed policy is not read-only for Golden Core command: {name}.")
                if isinstance(safety, dict) and safety.get("privilege_sensitive") is not False:
                    errors.append(f"Golden Core command is privilege-sensitive: {name}.")
                if isinstance(safety, dict) and safety.get("shares_external_data") is not False:
                    errors.append(f"Golden Core command shares external data: {name}.")
                if not isinstance(availability, dict) or availability.get("included_in_pypi") is not True:
                    errors.append(f"Golden Core command is not in the published package: {name}.")

    return errors


def report(
    registry: dict[str, Any],
    errors: list[str],
) -> dict[str, Any]:
    """Build one stable structured verifier result."""

    commands = registry.get("commands")
    names = [
        item.get("name")
        for item in commands
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    ] if isinstance(commands, list) else []
    lifecycle = load_json(LIFECYCLE_PATH, "command-lifecycle.json")
    lifecycle_commands = lifecycle.get("commands", {})
    stage_counts = Counter(
        lifecycle_commands.get(name, {}).get("stage", "unknown")
        for name in names
        if isinstance(lifecycle_commands, dict)
    )
    return {
        "success": not errors,
        "message": (
            f"QZX Golden Core candidate registry is valid for {len(names)} commands."
            if not errors
            else "QZX Golden Core candidate registry is invalid."
        ),
        "details": {
            "status": registry.get("status"),
            "target_maturity": registry.get("target_maturity"),
            "command_count": len(names),
            "commands": names,
            "current_stage_counts": dict(sorted(stage_counts.items())),
            "errors": errors,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--catalog",
        type=Path,
        help=(
            "Optional generated website command catalog for reviewed policy, "
            "availability, and external-effect validation."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print one machine-readable validation result.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        registry = load_golden_core()
        errors = validate_golden_core(
            registry,
            catalog_path=args.catalog.resolve() if args.catalog else None,
        )
        result = report(registry, errors)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exception:
        result = {
            "success": False,
            "message": "QZX Golden Core validation could not be completed.",
            "error": str(exception),
            "error_code": "golden_core_validation_failed",
            "details": {
                "errors": [str(exception)],
            },
        }

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(("[OK] " if result["success"] else "[FAIL] ") + result["message"])
        for error in result.get("details", {}).get("errors", []):
            print(f"  - {error}")
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
