#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Validate one QZX Golden Core release-quality attestation."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
REGISTRY_PATH = SOURCE_ROOT / "qzx" / "resources" / "golden-core.json"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.golden_core_release_quality_validation import (  # noqa: E402
    validate_release_quality,
)

def load_json(path: Path, label: str) -> dict[str, Any]:
    """Load one required JSON object."""

    with path.open("r", encoding="utf-8") as handle:
        document = json.load(handle)
    if not isinstance(document, dict):
        raise ValueError(f"{label} must contain a JSON object.")
    return document


def canonical_sha256(value: dict[str, Any]) -> str:
    """Return a deterministic content identity for one attestation payload."""

    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def load_registry() -> dict[str, Any]:
    return load_json(REGISTRY_PATH, "golden-core.json")


def configured_attestation_path(registry: dict[str, Any]) -> Path:
    policy = registry.get("release_quality_policy")
    if not isinstance(policy, dict):
        raise ValueError("Golden Core release_quality_policy is missing.")
    relative = policy.get("attestation_path")
    if not isinstance(relative, str) or not relative.strip():
        raise ValueError("Golden Core release-quality attestation_path is missing.")
    candidate = (PROJECT_ROOT / relative).resolve()
    try:
        candidate.relative_to(PROJECT_ROOT.resolve())
    except ValueError as exception:
        raise ValueError("Release-quality attestation path escapes the repository.") from exception
    return candidate


def attested_command_names(document: dict[str, Any]) -> list[str]:
    """Return the immutable command cohort recorded by one attestation."""

    commands = document.get("commands")
    if not isinstance(commands, dict):
        raise ValueError("Release-quality attestation commands must be an object.")
    names = [name for name in commands if isinstance(name, str) and name.strip()]
    if len(names) != 15 or len(set(names)) != 15 or len(names) != len(commands):
        raise ValueError("Release-quality attestation must contain 15 unique commands.")
    return names


def validate_attestation(
    document: dict[str, Any],
    *,
    registry: dict[str, Any] | None = None,
    verify_git: bool = False,
    verify_current_implementations: bool = False,
) -> list[str]:
    """Return deterministic validation errors for one release-quality record."""
    registry = registry if registry is not None else load_registry()
    return validate_release_quality(
        document,
        registry,
        attested_command_names=attested_command_names,
        canonical_sha256=canonical_sha256,
        verify_git=verify_git,
        verify_current_implementations=verify_current_implementations,
        project_root=PROJECT_ROOT,
    )

def report(document: dict[str, Any], errors: list[str]) -> dict[str, Any]:
    release = document.get("release") if isinstance(document.get("release"), dict) else {}
    commands = document.get("commands") if isinstance(document.get("commands"), dict) else {}
    return {
        "success": not errors,
        "message": (
            f"QZX Golden Core release quality is verified for {len(commands)} commands."
            if not errors
            else "QZX Golden Core release-quality attestation is invalid or stale."
        ),
        "details": {
            "version": release.get("version"),
            "tag": release.get("tag"),
            "source_revision": release.get("source_revision"),
            "command_count": len(commands),
            "attestation_sha256": document.get("attestation_sha256"),
            "errors": errors,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--attestation",
        type=Path,
        help="Release-quality JSON. Defaults to the path configured by Golden Core.",
    )
    parser.add_argument(
        "--verify-git",
        action="store_true",
        help="Additionally require the local annotated tag to resolve to source_revision.",
    )
    parser.add_argument(
        "--verify-current-implementations",
        action="store_true",
        help=(
            "Also compare the historical attestation with commands currently canonical "
            "in this checkout. This may intentionally fail after Alpha redesigns."
        ),
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable output.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        registry = load_registry()
        path = args.attestation.resolve() if args.attestation else configured_attestation_path(registry)
        document = load_json(path, "Golden Core release-quality attestation")
        errors = validate_attestation(
            document,
            registry=registry,
            verify_git=args.verify_git,
            verify_current_implementations=args.verify_current_implementations,
        )
        result = report(document, errors)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exception:
        result = {
            "success": False,
            "message": "QZX Golden Core release-quality validation could not be completed.",
            "details": {"errors": [str(exception)]},
        }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(("[OK] " if result["success"] else "[FAIL] ") + result["message"])
        for error in result.get("details", {}).get("errors", []):
            print(f"  - {error}")
    return 0 if result["success"] else 1
