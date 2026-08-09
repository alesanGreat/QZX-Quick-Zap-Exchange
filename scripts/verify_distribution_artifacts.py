#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Verify QZX wheel and source-distribution release contracts."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import tarfile
import zipfile
from email.parser import Parser
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
RESULT_CONTRACT_MANIFEST_PATH = (
    PROJECT_ROOT / "examples" / "result_contract" / "manifest.json"
)
RESULT_CONTRACT_EXAMPLES_ROOT = PROJECT_ROOT / "examples" / "result_contract"
RESULT_CONTRACT_WHEEL_PATH = (
    "qzx/resources/schemas/result-contract-v1.schema.json"
)
GOLDEN_CORE_WHEEL_PATH = "qzx/resources/golden-core.json"
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
    names = [
        item.get("name")
        for item in commands
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    ] if isinstance(commands, list) else []
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


def release_readme_marker(version: str) -> str:
    """Return the exact immutable-release statement required in metadata."""
    return f"This source release is QZX `{version}`"


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


def sha256(path: Path) -> str:
    """Return the hexadecimal SHA-256 digest of one artifact."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_release_contract() -> tuple[str, str]:
    """Read the candidate version and Python requirement from one source."""
    with PRODUCT_MANIFEST_PATH.open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    development = manifest["channels"]["development"]
    return development["version"], development["requires_python"]


def require_single_artifact(dist_dir: Path, pattern: str, label: str) -> Path:
    """Resolve exactly one candidate artifact without accepting ambiguity."""
    matches = sorted(dist_dir.glob(pattern))
    if len(matches) != 1:
        raise ValueError(
            f"Expected exactly one {label} matching {pattern!r} in "
            f"{dist_dir}, found {len(matches)}."
        )
    return matches[0]


def parse_metadata(text: str, context: str) -> dict[str, str]:
    """Validate the package identity fields shared by wheel and sdist."""
    metadata = Parser().parsestr(text)
    required = ("Name", "Version", "Requires-Python")
    missing = [field for field in required if not metadata.get(field)]
    if missing:
        raise ValueError(f"{context} metadata is missing: {', '.join(missing)}.")
    return {field: metadata[field] for field in required}


def verify_metadata(
    metadata: dict[str, str],
    *,
    expected_version: str,
    expected_python: str,
    context: str,
) -> None:
    """Reject artifacts whose core metadata differs from the release source."""
    expected = {
        "Name": "qzx",
        "Version": expected_version,
        "Requires-Python": expected_python,
    }
    differences = [
        f"{field}={metadata.get(field)!r}, expected {value!r}"
        for field, value in expected.items()
        if metadata.get(field) != value
    ]
    if differences:
        raise ValueError(f"{context} metadata differs: {'; '.join(differences)}.")


def verify_wheel(
    wheel_path: Path,
    *,
    expected_version: str,
    expected_python: str,
) -> dict[str, object]:
    """Inspect the wheel metadata and packaged long description."""
    with zipfile.ZipFile(wheel_path) as archive:
        names = set(archive.namelist())
        metadata_names = [
            name
            for name in names
            if name.endswith(".dist-info/METADATA")
        ]
        if len(metadata_names) != 1:
            raise ValueError(
                f"{wheel_path.name} must contain exactly one METADATA file."
            )
        missing_resources = [
            name
            for name in (RESULT_CONTRACT_WHEEL_PATH, GOLDEN_CORE_WHEEL_PATH)
            if name not in names
        ]
        if missing_resources:
            raise ValueError(
                f"{wheel_path.name} is missing packaged resources: "
                + ", ".join(missing_resources)
                + "."
            )
        metadata_text = archive.read(metadata_names[0]).decode("utf-8")
        result_contract_schema = archive.read(
            RESULT_CONTRACT_WHEEL_PATH
        ).decode("utf-8")
        golden_core_registry = archive.read(
            GOLDEN_CORE_WHEEL_PATH
        ).decode("utf-8")

    verify_metadata(
        parse_metadata(metadata_text, wheel_path.name),
        expected_version=expected_version,
        expected_python=expected_python,
        context=wheel_path.name,
    )
    if ATTRIBUTION not in metadata_text:
        raise ValueError(
            f"{wheel_path.name} does not contain the required attribution."
        )
    verify_release_description(
        metadata_text,
        expected_version=expected_version,
        context=wheel_path.name,
    )
    verify_package_index_links(metadata_text, wheel_path.name)
    verify_result_contract_schema(
        result_contract_schema,
        f"{wheel_path.name}:{RESULT_CONTRACT_WHEEL_PATH}",
    )
    golden_core_commands = verify_golden_core_registry(
        golden_core_registry,
        f"{wheel_path.name}:{GOLDEN_CORE_WHEEL_PATH}",
    )
    return {
        "filename": wheel_path.name,
        "size_bytes": wheel_path.stat().st_size,
        "sha256": sha256(wheel_path),
        "result_contract_schema": RESULT_CONTRACT_SCHEMA_ID,
        "golden_core_commands": golden_core_commands,
    }


def verify_sdist(
    sdist_path: Path,
    *,
    expected_version: str,
    expected_python: str,
) -> dict[str, object]:
    """Inspect sdist metadata, attribution, and Unix launcher mode."""
    root = f"qzx-{expected_version}"
    with tarfile.open(sdist_path, "r:gz") as archive:
        members = {member.name: member for member in archive.getmembers()}
        launcher_name = f"{root}/qzx.sh"
        launcher = members.get(launcher_name)
        if launcher is None or not launcher.isfile():
            raise ValueError(
                f"{sdist_path.name} has no regular {launcher_name} launcher."
            )
        launcher_mode = launcher.mode & 0o777
        if launcher_mode != 0o755:
            raise ValueError(
                f"{sdist_path.name} stores qzx.sh as {launcher_mode:04o}; "
                "release source distributions require 0755."
            )

        metadata_member = members.get(f"{root}/PKG-INFO")
        readme_member = members.get(f"{root}/README.md")
        codemeta_name = f"{root}/codemeta.json"
        citation_name = f"{root}/CITATION.cff"
        citation_sync_name = f"{root}/scripts/sync_citation.py"
        codemeta_sync_name = f"{root}/scripts/sync_codemeta.py"
        schema_name = (
            f"{root}/src/qzx/resources/schemas/"
            "result-contract-v1.schema.json"
        )
        specification_name = f"{root}/docs/result-contract-v1.md"
        adoption_name = f"{root}/docs/result-contract-adoption.md"
        quickstart_name = f"{root}/docs/result-contract-quickstart.md"
        validator_name = f"{root}/scripts/validate_result_contract.py"
        mcp_validator_name = f"{root}/scripts/validate_mcp_result_contract.py"
        evidence_validator_name = (
            f"{root}/scripts/validate_result_contract_evidence.py"
        )
        conformance_runner_name = (
            f"{root}/scripts/run_result_contract_conformance.py"
        )
        action_metadata_name = (
            f"{root}/.github/actions/result-contract-conformance/action.yml"
        )
        action_runner_name = (
            f"{root}/.github/actions/result-contract-conformance/run.py"
        )
        action_readme_name = (
            f"{root}/.github/actions/result-contract-conformance/README.md"
        )
        golden_core_name = f"{root}/src/qzx/resources/golden-core.json"
        golden_core_doc_name = f"{root}/docs/golden-core.md"
        golden_core_verifier_name = f"{root}/scripts/verify_golden_core.py"
        platform_capture_name = (
            f"{root}/scripts/capture_golden_core_platform_evidence.py"
        )
        platform_merge_name = (
            f"{root}/scripts/merge_golden_core_platform_evidence.py"
        )
        adopters_name = f"{root}/ADOPTERS.md"
        conformance_manifest_name = (
            f"{root}/examples/result_contract/manifest.json"
        )
        example_names = [
            f"{root}/{path.relative_to(PROJECT_ROOT).as_posix()}"
            for path in sorted(RESULT_CONTRACT_EXAMPLES_ROOT.iterdir())
            if path.is_file() and path.suffix.lower() in {".json", ".md"}
        ]
        readme_link_names = [
            f"{root}/{relative_path}"
            for relative_path in canonical_readme_relative_files()
        ]
        required_members = {
            "PKG-INFO": metadata_member,
            "README.md": readme_member,
            codemeta_name: members.get(codemeta_name),
            citation_name: members.get(citation_name),
            citation_sync_name: members.get(citation_sync_name),
            codemeta_sync_name: members.get(codemeta_sync_name),
            schema_name: members.get(schema_name),
            specification_name: members.get(specification_name),
            adoption_name: members.get(adoption_name),
            quickstart_name: members.get(quickstart_name),
            validator_name: members.get(validator_name),
            mcp_validator_name: members.get(mcp_validator_name),
            evidence_validator_name: members.get(evidence_validator_name),
            conformance_runner_name: members.get(conformance_runner_name),
            action_metadata_name: members.get(action_metadata_name),
            action_runner_name: members.get(action_runner_name),
            action_readme_name: members.get(action_readme_name),
            golden_core_name: members.get(golden_core_name),
            golden_core_doc_name: members.get(golden_core_doc_name),
            golden_core_verifier_name: members.get(golden_core_verifier_name),
            platform_capture_name: members.get(platform_capture_name),
            platform_merge_name: members.get(platform_merge_name),
            adopters_name: members.get(adopters_name),
            conformance_manifest_name: members.get(conformance_manifest_name),
            **{name: members.get(name) for name in example_names},
            **{name: members.get(name) for name in readme_link_names},
        }
        missing = [
            name
            for name, member in required_members.items()
            if member is None or not member.isfile()
        ]
        if missing:
            raise ValueError(
                f"{sdist_path.name} is missing required release files: "
                + ", ".join(missing)
                + "."
            )
        metadata_handle = archive.extractfile(metadata_member)
        readme_handle = archive.extractfile(readme_member)
        codemeta_handle = archive.extractfile(required_members[codemeta_name])
        citation_handle = archive.extractfile(required_members[citation_name])
        schema_handle = archive.extractfile(required_members[schema_name])
        golden_core_handle = archive.extractfile(
            required_members[golden_core_name]
        )
        conformance_handle = archive.extractfile(
            required_members[conformance_manifest_name]
        )
        if (
            metadata_handle is None
            or readme_handle is None
            or codemeta_handle is None
            or citation_handle is None
            or schema_handle is None
            or golden_core_handle is None
            or conformance_handle is None
        ):
            raise ValueError(f"{sdist_path.name} contains unreadable metadata.")
        metadata_text = metadata_handle.read().decode("utf-8")
        readme_text = readme_handle.read().decode("utf-8")
        codemeta_text = codemeta_handle.read().decode("utf-8")
        citation_text = citation_handle.read().decode("utf-8")
        result_contract_schema = schema_handle.read().decode("utf-8")
        golden_core_registry = golden_core_handle.read().decode("utf-8")
        conformance_manifest = conformance_handle.read().decode("utf-8")

    verify_metadata(
        parse_metadata(metadata_text, sdist_path.name),
        expected_version=expected_version,
        expected_python=expected_python,
        context=sdist_path.name,
    )
    if codemeta_text != CODEMETA_PATH.read_text(encoding="utf-8"):
        raise ValueError(
            f"{sdist_path.name} codemeta.json diverges from the repository projection."
        )
    if citation_text != CITATION_PATH.read_text(encoding="utf-8"):
        raise ValueError(
            f"{sdist_path.name} CITATION.cff diverges from the repository citation."
        )
    if ATTRIBUTION not in readme_text or ATTRIBUTION not in metadata_text:
        raise ValueError(
            f"{sdist_path.name} does not contain the required attribution."
        )
    verify_release_description(
        metadata_text,
        expected_version=expected_version,
        context=f"{sdist_path.name} PKG-INFO",
    )
    verify_package_index_links(
        metadata_text,
        f"{sdist_path.name} PKG-INFO",
    )
    verify_release_description(
        readme_text,
        expected_version=expected_version,
        context=f"{sdist_path.name} README.md",
    )
    verify_result_contract_schema(
        result_contract_schema,
        f"{sdist_path.name}:{schema_name}",
    )
    golden_core_commands = verify_golden_core_registry(
        golden_core_registry,
        f"{sdist_path.name}:{golden_core_name}",
    )
    conformance_cases = verify_conformance_manifest(
        conformance_manifest,
        f"{sdist_path.name}:{conformance_manifest_name}",
    )
    return {
        "filename": sdist_path.name,
        "size_bytes": sdist_path.stat().st_size,
        "sha256": sha256(sdist_path),
        "qzx_sh_mode": f"{launcher_mode:04o}",
        "result_contract_schema": RESULT_CONTRACT_SCHEMA_ID,
        "golden_core_commands": golden_core_commands,
        "result_contract_conformance_cases": conformance_cases,
    }


def verify_distributions(
    dist_dir: Path,
    *,
    expected_version: str,
    expected_python: str,
) -> dict[str, object]:
    """Verify the exact wheel and sdist for one QZX candidate."""
    wheel = require_single_artifact(
        dist_dir,
        f"qzx-{expected_version}-py3-none-any.whl",
        "wheel",
    )
    sdist = require_single_artifact(
        dist_dir,
        f"qzx-{expected_version}.tar.gz",
        "source distribution",
    )
    artifacts = [
        verify_wheel(
            wheel,
            expected_version=expected_version,
            expected_python=expected_python,
        ),
        verify_sdist(
            sdist,
            expected_version=expected_version,
            expected_python=expected_python,
        ),
    ]
    return {
        "success": True,
        "message": (
            f"Verified QZX {expected_version} wheel and source distribution."
        ),
        "version": expected_version,
        "requires_python": expected_python,
        "artifacts": artifacts,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dist-dir",
        type=Path,
        default=PROJECT_ROOT / "dist",
        help="Directory containing the wheel and .tar.gz candidate.",
    )
    parser.add_argument(
        "--version",
        help="Expected version; defaults to channels.development.version.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print one stable JSON document.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest_version, expected_python = load_release_contract()
    expected_version = args.version or manifest_version
    try:
        result = verify_distributions(
            args.dist_dir.resolve(),
            expected_version=expected_version,
            expected_python=expected_python,
        )
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exception:
        result = {
            "success": False,
            "message": f"Distribution verification failed: {exception}",
            "version": expected_version,
            "requires_python": expected_python,
            "artifacts": [],
        }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    else:
        print(("[OK] " if result["success"] else "[FAIL] ") + result["message"])
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
