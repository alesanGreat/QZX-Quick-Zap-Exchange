#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Shared release-contract and README validation for distribution artifacts."""

from __future__ import annotations

import json
import re
from pathlib import Path, PurePosixPath
from urllib.parse import quote, urlsplit


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PRODUCT_MANIFEST_PATH = (
    PROJECT_ROOT / "src" / "qzx" / "resources" / "product-manifest.json"
)
CODEMETA_PATH = PROJECT_ROOT / "codemeta.json"
CITATION_PATH = PROJECT_ROOT / "CITATION.cff"
README_PATH = PROJECT_ROOT / "README.md"
ATTRIBUTION = (
    "QZX — Quick Zap Exchange, created and maintained by Alejandro Sánchez."
)
RESULT_CONTRACT_SCHEMA_ID = (
    "https://qzx.yumbale.com/schemas/result-contract-v1.schema.json"
)
CONFORMANCE_RECEIPT_SCHEMA_ID = (
    "https://qzx.yumbale.com/schemas/"
    "result-contract-conformance-receipt-v1.schema.json"
)
RESULT_CONTRACT_MANIFEST_PATH = (
    PROJECT_ROOT / "examples" / "result_contract" / "manifest.json"
)
RESULT_CONTRACT_EXAMPLES_ROOT = PROJECT_ROOT / "examples" / "result_contract"
RESULT_CONTRACT_EXAMPLE_SUFFIXES = frozenset(
    {
        ".cs",
        ".csproj",
        ".go",
        ".in",
        ".java",
        ".json",
        ".md",
        ".mod",
        ".mjs",
        ".cmd",
        ".properties",
        ".py",
        ".sum",
        ".ts",
        ".txt",
        ".xml",
        ".yaml",
    }
)
RESULT_CONTRACT_WHEEL_PATH = (
    "qzx/resources/schemas/result-contract-v1.schema.json"
)
CONFORMANCE_RECEIPT_WHEEL_PATH = (
    "qzx/resources/schemas/result-contract-conformance-receipt-v1.schema.json"
)
GOLDEN_CORE_WHEEL_PATH = "qzx/resources/golden-core.json"
DISTRIBUTION_VERIFIER_SUPPORT_FILES = (
    "scripts/verify_distribution_artifacts.py",
    "scripts/distribution_artifact_contract.py",
    "scripts/distribution_artifact_wheel.py",
    "scripts/distribution_artifact_sdist.py",
)
SDIST_REQUIRED_RELEASE_FILES = (
    "codemeta.json",
    "CITATION.cff",
    "scripts/sync_citation.py",
    "scripts/sync_codemeta.py",
    "src/qzx/resources/schemas/result-contract-v1.schema.json",
    "src/qzx/resources/schemas/result-contract-conformance-receipt-v1.schema.json",
    "docs/result-contract-v1.md",
    "docs/result-contract-adoption.md",
    "docs/result-contract-quickstart.md",
    "scripts/validate_result_contract.py",
    "scripts/validate_mcp_result_contract.py",
    "scripts/validate_result_contract_evidence.py",
    "scripts/run_result_contract_conformance.py",
    "action.yml",
    ".github/actions/result-contract-conformance/action.yml",
    ".github/actions/result-contract-conformance/run.py",
    ".github/actions/result-contract-conformance/README.md",
    "src/qzx/resources/golden-core.json",
    "docs/golden-core.md",
    "scripts/verify_golden_core.py",
    "scripts/capture_golden_core_platform_evidence.py",
    "scripts/merge_golden_core_platform_evidence.py",
    "ADOPTERS.md",
    "examples/result_contract/manifest.json",
    "native/project_languages/Cargo.toml",
    "native/project_languages/Cargo.lock",
    "native/project_languages/src/lib.rs",
    "scripts/smoke_native_project_languages.py",
    *DISTRIBUTION_VERIFIER_SUPPORT_FILES,
)
_INLINE_MARKDOWN_DESTINATION = re.compile(
    r"(?P<prefix>\]\()"
    r"(?P<destination><[^>\r\n]+>|[^)\s]+)"
    r"(?P<suffix>(?:\s+(?:\"[^\"\r\n]*\"|'[^'\r\n]*'|\([^\)\r\n]*\)))?\))"
)
_REFERENCE_MARKDOWN_DESTINATION = re.compile(
    r"^(?P<prefix>[ \t]{0,3}\[[^\]\r\n]+\]:[ \t]*)"
    r"(?P<destination><[^>\r\n]+>|\S+)"
    r"(?P<suffix>[ \t]*(?:\"[^\"\r\n]*\"|'[^'\r\n]*'|\([^\)\r\n]*\))?[ \t]*)$",
    re.MULTILINE,
)


def _unwrap_markdown_destination(destination: str) -> tuple[str, bool]:
    if destination.startswith("<") and destination.endswith(">"):
        return destination[1:-1], True
    return destination, False


def is_repository_relative_destination(destination: str) -> bool:
    """Return whether one Markdown destination depends on repository context."""
    raw, _ = _unwrap_markdown_destination(destination)
    if not raw or raw.startswith(("#", "/", "\\")):
        return False
    parsed = urlsplit(raw)
    return not parsed.scheme and not parsed.netloc


def _repository_url_for_destination(
    destination: str,
    *,
    repository_url: str,
    revision: str,
) -> str:
    raw, wrapped = _unwrap_markdown_destination(destination)
    if not is_repository_relative_destination(destination):
        return destination

    parsed = urlsplit(raw)
    parts: list[str] = []
    for part in PurePosixPath(parsed.path).parts:
        if part in ("", "."):
            continue
        if part == "..":
            raise ValueError(
                f"Package README link escapes the repository root: {destination!r}."
            )
        parts.append(part)
    if not parts:
        return destination

    encoded_path = quote(
        "/".join(parts),
        safe="/%:@!$&'()*+,;=-._~",
    )
    encoded_revision = quote(revision, safe="")
    absolute = (
        f"{repository_url.rstrip('/')}/blob/{encoded_revision}/{encoded_path}"
    )
    if parsed.query:
        absolute += f"?{parsed.query}"
    if parsed.fragment:
        absolute += f"#{parsed.fragment}"
    return f"<{absolute}>" if wrapped else absolute


def find_repository_relative_links(markdown: str) -> list[str]:
    """Return repository-relative inline and reference Markdown destinations."""
    destinations: list[str] = []
    for pattern in (_INLINE_MARKDOWN_DESTINATION, _REFERENCE_MARKDOWN_DESTINATION):
        destinations.extend(
            match.group("destination")
            for match in pattern.finditer(markdown)
            if is_repository_relative_destination(match.group("destination"))
        )
    return destinations


def canonical_readme_relative_files() -> list[str]:
    """Return every repository file referenced relatively by the canonical README."""
    try:
        markdown = README_PATH.read_text(encoding="utf-8")
    except OSError as exception:
        raise ValueError("The canonical QZX README is unreadable.") from exception

    relative_files: set[str] = set()
    for destination in find_repository_relative_links(markdown):
        raw, _ = _unwrap_markdown_destination(destination)
        parsed = urlsplit(raw)
        parts: list[str] = []
        for part in PurePosixPath(parsed.path).parts:
            if part in ("", "."):
                continue
            if part == "..":
                raise ValueError(
                    f"README link escapes the repository root: {destination!r}."
                )
            parts.append(part)
        if not parts:
            continue
        source = PROJECT_ROOT.joinpath(*parts)
        relative = PurePosixPath(*parts).as_posix()
        if not source.is_file():
            raise ValueError(
                f"README relative link does not resolve to a repository file: {relative}."
            )
        relative_files.add(relative)
    return sorted(relative_files)


def render_package_readme(
    markdown: str,
    *,
    repository_url: str,
    revision: str,
) -> str:
    """Convert repository-relative Markdown links to immutable repository URLs."""
    if not repository_url.startswith(("https://", "http://")):
        raise ValueError("repository_url must be an absolute HTTP(S) URL.")
    if not revision.strip():
        raise ValueError("revision must not be empty.")

    def replace(match: re.Match[str]) -> str:
        destination = _repository_url_for_destination(
            match.group("destination"),
            repository_url=repository_url,
            revision=revision,
        )
        return f"{match.group('prefix')}{destination}{match.group('suffix')}"

    rendered = _INLINE_MARKDOWN_DESTINATION.sub(replace, markdown)
    return _REFERENCE_MARKDOWN_DESTINATION.sub(replace, rendered)


def verify_golden_core_registry(text: str, context: str) -> int:
    """Reject artifacts without the canonical Golden Core candidate registry."""
    try:
        registry = json.loads(text)
    except json.JSONDecodeError as exception:
        raise ValueError(f"{context} contains invalid Golden Core JSON.") from exception
    commands = registry.get("commands") if isinstance(registry, dict) else None
    names = (
        [
            item.get("name")
            for item in commands
            if isinstance(item, dict) and isinstance(item.get("name"), str)
        ]
        if isinstance(commands, list)
        else []
    )
    if (
        not isinstance(registry, dict)
        or registry.get("schema_version") != 1
        or registry.get("name") != "QZX Golden Core"
        or registry.get("status") != "candidate"
        or registry.get("target_maturity") != "beta"
        or len(names) != 15
        or len(set(names)) != len(names)
    ):
        raise ValueError(
            f"{context} does not contain the canonical 15-command "
            "QZX Golden Core candidate registry."
        )
    return len(names)


def load_canonical_conformance_manifest() -> dict[str, object]:
    """Load the repository's single source of truth for conformance fixtures."""
    try:
        manifest = json.loads(
            RESULT_CONTRACT_MANIFEST_PATH.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exception:
        raise ValueError(
            "The canonical QZX Result Contract conformance manifest is unreadable."
        ) from exception
    if not isinstance(manifest, dict):
        raise ValueError(
            "The canonical QZX Result Contract conformance manifest is malformed."
        )
    return manifest


def verify_conformance_manifest(text: str, context: str) -> int:
    """Reject sdists whose v1 fixture manifest diverges from the source tree."""
    try:
        manifest = json.loads(text)
    except json.JSONDecodeError as exception:
        raise ValueError(f"{context} contains invalid conformance JSON.") from exception
    cases = manifest.get("cases") if isinstance(manifest, dict) else None
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema_version") != 1
        or manifest.get("contract") != RESULT_CONTRACT_SCHEMA_ID
        or not isinstance(cases, list)
    ):
        raise ValueError(f"{context} is not the QZX Result Contract v1 suite.")
    for case in cases:
        if (
            not isinstance(case, dict)
            or not isinstance(case.get("id"), str)
            or not isinstance(case.get("file"), str)
            or not isinstance(case.get("expected_conformant"), bool)
            or not isinstance(case.get("expected_violations"), list)
        ):
            raise ValueError(f"{context} contains a malformed conformance case.")

    canonical = load_canonical_conformance_manifest()
    if manifest != canonical:
        raise ValueError(
            f"{context} does not match the canonical Result Contract manifest."
        )
    return len(cases)


def verify_result_contract_schema(text: str, context: str) -> None:
    """Reject artifacts without the canonical QZX Result Contract v1 schema."""
    try:
        schema = json.loads(text)
    except json.JSONDecodeError as exception:
        raise ValueError(f"{context} contains invalid JSON Schema.") from exception
    if (
        not isinstance(schema, dict)
        or schema.get("$id") != RESULT_CONTRACT_SCHEMA_ID
        or schema.get("$schema")
        != "https://json-schema.org/draft/2020-12/schema"
        or schema.get("required") != ["success", "message"]
        or schema.get("additionalProperties") is not True
    ):
        raise ValueError(
            f"{context} does not contain QZX Result Contract v1."
        )


def _mapping(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _receipt_schema_facts(schema: dict[str, object]) -> dict[str, object]:
    properties = _mapping(schema.get("properties"))
    warnings = _mapping(properties.get("warnings"))
    details = _mapping(properties.get("details"))
    detail_properties = _mapping(details.get("properties"))
    failure_rules = schema.get("allOf")
    failure_rule = (
        failure_rules[0]
        if isinstance(failure_rules, list)
        and len(failure_rules) == 1
        and isinstance(failure_rules[0], dict)
        else {}
    )
    failure_if = _mapping(failure_rule.get("if"))
    failure_then = _mapping(failure_rule.get("then"))
    failure_properties = _mapping(failure_if.get("properties"))
    return {
        "properties": properties,
        "warning_items": _mapping(warnings.get("items")),
        "detail_properties": detail_properties,
        "cases": _mapping(detail_properties.get("cases")),
        "failure_success": _mapping(failure_properties.get("success")),
        "failure_if_required": failure_if.get("required"),
        "failure_then_required": failure_then.get("required"),
    }


def verify_conformance_receipt_schema(text: str, context: str) -> None:
    """Reject artifacts without the canonical QZX conformance receipt schema."""
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exception:
        raise ValueError(f"{context} contains invalid JSON Schema.") from exception
    schema = _mapping(parsed)
    facts = _receipt_schema_facts(schema)
    properties = facts["properties"]
    details = facts["detail_properties"]
    checks = (
        isinstance(parsed, dict),
        schema.get("$id") == CONFORMANCE_RECEIPT_SCHEMA_ID,
        schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema",
        schema.get("required")
        == ["receipt_schema", "success", "message", "warnings", "details"],
        _mapping(properties.get("receipt_schema")).get("const")
        == CONFORMANCE_RECEIPT_SCHEMA_ID,
        _mapping(properties.get("success")).get("type") == "boolean",
        _mapping(properties.get("message")).get("minLength") == 1,
        _mapping(properties.get("message")).get("pattern") == r"\S",
        facts["warning_items"].get("minLength") == 1,
        facts["warning_items"].get("pattern") == r"\S",
        _mapping(properties.get("error_code")).get("pattern")
        == "^[a-z][a-z0-9_]*$",
        facts["failure_success"].get("const") is False,
        facts["failure_if_required"] == ["success"],
        facts["failure_then_required"] == ["error_code"],
        details.get("report_schema_version", {}).get("const") == 1,
        details.get("contract_schema", {}).get("const") == RESULT_CONTRACT_SCHEMA_ID,
        facts["cases"].get("minItems") == 2,
        facts["cases"].get("maxItems") == 2,
        schema.get("additionalProperties") is False,
    )
    if not all(checks):
        raise ValueError(
            f"{context} does not contain QZX Result Contract Conformance Receipt v1."
        )


def release_readme_marker(version: str) -> str:
    """Return the exact immutable-release statement required in metadata."""
    return f"This source release is QZX \x60{version}\x60"


def verify_release_description(
    text: str,
    *,
    expected_version: str,
    context: str,
) -> None:
    """Reject package descriptions that do not identify their own release."""
    marker = release_readme_marker(expected_version)
    if marker not in text:
        raise ValueError(
            f"{context} does not identify its immutable source release; "
            f"expected {marker!r}."
        )


def verify_package_index_links(text: str, context: str) -> None:
    """Reject Markdown links that a package index would resolve against itself."""
    patterns = (
        re.compile(
            r"\]\((?P<destination><[^>\r\n]+>|[^)\s]+)"
            r"(?:\s+(?:\"[^\"\r\n]*\"|'[^'\r\n]*'|\([^\)\r\n]*\)))?\)"
        ),
        re.compile(
            r"^[ \t]{0,3}\[[^\]\r\n]+\]:[ \t]*"
            r"(?P<destination><[^>\r\n]+>|\S+)",
            re.MULTILINE,
        ),
    )
    relative: list[str] = []
    for pattern in patterns:
        for match in pattern.finditer(text):
            destination = match.group("destination")
            raw = (
                destination[1:-1]
                if destination.startswith("<") and destination.endswith(">")
                else destination
            )
            if not raw or raw.startswith(("#", "/", "\\")):
                continue
            parsed = urlsplit(raw)
            if not parsed.scheme and not parsed.netloc:
                relative.append(destination)
    if relative:
        destinations = ", ".join(sorted(set(relative)))
        raise ValueError(
            f"{context} contains repository-relative Markdown links that "
            f"PyPI cannot resolve: {destinations}."
        )
