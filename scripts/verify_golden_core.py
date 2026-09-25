#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Validate the public QZX Golden Core candidate registry."""

from __future__ import annotations

import argparse
import json
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
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.golden_core_registry_validation import (  # noqa: E402
    command_registry_context,
    validate_catalog,
    validate_commands,
    validate_failure_policy,
    validate_readiness_dimensions,
    validate_registry_metadata,
    validate_release_quality_policy,
)


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

    errors = []
    errors.extend(validate_registry_metadata(registry))
    errors.extend(validate_readiness_dimensions(registry))

    (
        indexed_names,
        lifecycle_commands,
        lifecycle_stages,
        context_errors,
    ) = command_registry_context(command_index, lifecycle)
    errors.extend(context_errors)

    command_names, command_errors = validate_commands(
        registry,
        indexed_names,
        lifecycle_commands,
        lifecycle_stages,
    )
    errors.extend(command_errors)
    errors.extend(validate_failure_policy(registry, command_names))
    errors.extend(validate_release_quality_policy(registry))

    if catalog_path is not None:
        catalog = load_json(catalog_path, "generated command catalog")
        errors.extend(validate_catalog(catalog, command_names))
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
