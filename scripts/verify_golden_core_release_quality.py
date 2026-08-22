#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Validate one QZX Golden Core release-quality attestation."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
REGISTRY_PATH = SOURCE_ROOT / "qzx" / "resources" / "golden-core.json"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from qzx.core.command_loader import CommandLoader  # noqa: E402
from qzx.core.implementation_digest import command_implementation_digest  # noqa: E402


_SHA256_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_REQUIRED_QUALITY_GATES = (
    "exact_release_tag_verified",
    "distribution_artifacts_verified",
    "twine_check_passed",
    "pypi_artifacts_verified",
    "github_release_assets_verified",
    "ci_matrix_passed",
    "digest_bound_platform_evidence_verified",
    "result_contract_verified",
    "zero_known_release_blockers",
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


def _valid_sha256(value: Any) -> bool:
    return isinstance(value, str) and _SHA256_PATTERN.fullmatch(value) is not None


def _nonempty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_attestation(
    document: dict[str, Any],
    *,
    registry: dict[str, Any] | None = None,
    verify_git: bool = False,
    verify_current_implementations: bool = False,
) -> list[str]:
    """Return deterministic validation errors for one release-quality record."""

    registry = registry if registry is not None else load_registry()
    errors: list[str] = []
    try:
        names = attested_command_names(document)
    except ValueError as exception:
        names = []
        errors.append(str(exception))
    policy = registry.get("release_quality_policy")
    if not isinstance(policy, dict):
        return ["Golden Core release_quality_policy is missing."]

    expected_policy_flags = (
        "requires_exact_release_tag",
        "requires_verified_distribution_hashes",
        "requires_successful_ci",
        "requires_digest_bound_platform_evidence",
        "requires_zero_known_release_blockers",
    )
    for flag in expected_policy_flags:
        if policy.get(flag) is not True:
            errors.append(f"Golden Core release-quality policy must enable {flag}.")
    blocking_label = policy.get("blocking_issue_label")
    if not _nonempty_text(blocking_label):
        errors.append("Golden Core release-quality policy needs a blocking issue label.")

    if document.get("schema_version") != 1:
        errors.append("Release-quality attestation must use schema_version 1.")
    if document.get("evidence_type") != "qzx_golden_core_release_quality":
        errors.append("Release-quality attestation has an unexpected evidence_type.")
    if document.get("status") != "verified":
        errors.append("Release-quality attestation status must be verified.")
    if not _nonempty_text(document.get("evidence_scope")):
        errors.append("Release-quality evidence_scope must be non-empty text.")
    limitations = document.get("limitations")
    if not isinstance(limitations, list) or len(limitations) < 2 or not all(
        _nonempty_text(item) for item in limitations
    ):
        errors.append("Release-quality attestation must disclose at least two limitations.")

    release = document.get("release")
    if not isinstance(release, dict):
        errors.append("Release-quality attestation has no release object.")
        release = {}
    version = release.get("version")
    tag = release.get("tag")
    source_revision = release.get("source_revision")
    if not _nonempty_text(version):
        errors.append("Release-quality version must be non-empty text.")
    if not isinstance(tag, str) or tag != f"v{version}":
        errors.append("Release-quality tag must be v<version>.")
    if not isinstance(source_revision, str) or _COMMIT_PATTERN.fullmatch(source_revision) is None:
        errors.append("Release-quality source_revision must be a 40-character Git SHA.")
    if release.get("status") != "Alpha":
        errors.append("Golden Core release-quality evidence currently expects an Alpha release.")
    if not _nonempty_text(release.get("released_at")):
        errors.append("Release-quality released_at must be non-empty text.")

    pypi = release.get("pypi")
    github = release.get("github")
    if not isinstance(pypi, dict):
        errors.append("Release-quality attestation has no PyPI evidence.")
        pypi = {}
    if not isinstance(github, dict):
        errors.append("Release-quality attestation has no GitHub Release evidence.")
        github = {}
    if pypi.get("published") is not True:
        errors.append("PyPI evidence must confirm the exact release is published.")
    if pypi.get("requires_python") != ">=3.13":
        errors.append("PyPI evidence must confirm requires_python >=3.13.")
    if github.get("prerelease") is not True or github.get("draft") is not False:
        errors.append("GitHub evidence must describe a published pre-release, not a draft.")
    if not isinstance(github.get("asset_count"), int) or github.get("asset_count", 0) < 3:
        errors.append("GitHub Release must expose at least wheel, sdist, and platform summary.")

    artifacts = release.get("artifacts")
    if not isinstance(artifacts, dict):
        errors.append("Release-quality attestation has no artifact map.")
        artifacts = {}
    expected_filenames = {
        "wheel": f"qzx-{version}-py3-none-any.whl",
        "sdist": f"qzx-{version}.tar.gz",
    }
    for kind, expected_filename in expected_filenames.items():
        artifact = artifacts.get(kind)
        if not isinstance(artifact, dict):
            errors.append(f"Release-quality attestation is missing {kind} evidence.")
            continue
        if artifact.get("filename") != expected_filename:
            errors.append(f"Release-quality {kind} filename does not match the release version.")
        if not _valid_sha256(artifact.get("sha256")):
            errors.append(f"Release-quality {kind} SHA-256 is invalid.")

    ci = document.get("ci")
    if not isinstance(ci, dict):
        errors.append("Release-quality attestation has no CI evidence.")
        ci = {}
    if ci.get("conclusion") != "success":
        errors.append("Release-quality CI conclusion must be success.")
    if ci.get("source_revision") != source_revision:
        errors.append("Release-quality CI source revision differs from the release tag revision.")
    run_id = ci.get("run_id")
    if not isinstance(run_id, int) or run_id <= 0:
        errors.append("Release-quality CI run_id must be a positive integer.")
    environment_count = ci.get("environment_count")
    command_runs = ci.get("command_environment_runs")
    if not isinstance(environment_count, int) or environment_count < 3:
        errors.append("Release-quality CI must cover at least three environments.")
    if (
        isinstance(environment_count, int)
        and command_runs != len(names) * environment_count
    ):
        errors.append("Release-quality CI command/environment run count is inconsistent.")
    if ci.get("failed_command_runs") != 0:
        errors.append("Release-quality CI must report zero failed Golden Core command runs.")
    for field in ("platform_aggregate_sha256", "platform_summary_file_sha256"):
        if not _valid_sha256(ci.get(field)):
            errors.append(f"Release-quality CI {field} is invalid.")

    commands = document.get("commands")
    if not isinstance(commands, dict) or set(commands) != set(names):
        errors.append("Release-quality command map is malformed.")
        commands = {}
    for name in names:
        record = commands.get(name)
        if not isinstance(record, dict):
            errors.append(f"Release-quality command record is missing: {name}.")
            continue
        if not _valid_sha256(record.get("implementation_digest")):
            errors.append(f"Release-quality implementation digest is invalid for {name}.")
        if record.get("release_blockers") != []:
            errors.append(f"Release-quality command has unresolved blockers: {name}.")

    if verify_current_implementations:
        loader = CommandLoader()
        for name in names:
            command = loader.get_command(name)
            if command is None:
                errors.append(
                    f"Attested command is no longer a current canonical command: {name}."
                )
                continue
            record = commands.get(name)
            if not isinstance(record, dict):
                continue
            current_digest = command_implementation_digest(type(command))
            if record.get("implementation_digest") != current_digest:
                errors.append(
                    f"Release-quality implementation digest is stale for current {name}."
                )

    quality_gates = document.get("quality_gates")
    if not isinstance(quality_gates, dict):
        errors.append("Release-quality quality_gates must be an object.")
        quality_gates = {}
    for gate in _REQUIRED_QUALITY_GATES:
        if quality_gates.get(gate) is not True:
            errors.append(f"Release-quality gate is not verified: {gate}.")
    if quality_gates.get("blocking_issue_label") != blocking_label:
        errors.append("Release-quality blocking issue label differs from Golden Core policy.")
    if quality_gates.get("known_release_blockers") != []:
        errors.append("Release-quality attestation must contain zero known release blockers.")
    nonblocking = quality_gates.get("open_nonblocking_work")
    if not isinstance(nonblocking, list):
        errors.append("Release-quality open_nonblocking_work must be an array.")
    else:
        for item in nonblocking:
            if not isinstance(item, dict) or item.get("blocking") is not False:
                errors.append("Release-quality nonblocking work must be explicit non-blocking records.")
                break

    observed_attestation_hash = document.get("attestation_sha256")
    payload = dict(document)
    payload.pop("attestation_sha256", None)
    expected_attestation_hash = canonical_sha256(payload)
    if observed_attestation_hash != expected_attestation_hash:
        errors.append("Release-quality attestation SHA-256 is invalid.")

    if verify_git and isinstance(tag, str) and isinstance(source_revision, str):
        completed = subprocess.run(
            ["git", "rev-list", "-n", "1", tag],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=30,
        )
        if completed.returncode != 0:
            errors.append(f"Git could not resolve release-quality tag {tag}.")
        elif completed.stdout.strip() != source_revision:
            errors.append("Release-quality tag does not resolve to source_revision.")

    return errors


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


if __name__ == "__main__":
    raise SystemExit(main())
