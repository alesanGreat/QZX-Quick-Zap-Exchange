#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Source-distribution validation for QZX release candidates."""

from __future__ import annotations

import tarfile
from pathlib import Path

try:
    from scripts.distribution_artifact_contract import (
        ATTRIBUTION,
        CITATION_PATH,
        CODEMETA_PATH,
        CONFORMANCE_RECEIPT_SCHEMA_ID,
        PROJECT_ROOT,
        RESULT_CONTRACT_EXAMPLE_SUFFIXES,
        RESULT_CONTRACT_EXAMPLES_ROOT,
        RESULT_CONTRACT_SCHEMA_ID,
        SDIST_REQUIRED_RELEASE_FILES,
        canonical_readme_relative_files,
        verify_conformance_manifest,
        verify_conformance_receipt_schema,
        verify_golden_core_registry,
        verify_package_index_links,
        verify_release_description,
        verify_result_contract_schema,
    )
    from scripts.distribution_artifact_wheel import (
        parse_metadata,
        sha256,
        verify_metadata,
    )
except ModuleNotFoundError:
    from distribution_artifact_contract import (
        ATTRIBUTION,
        CITATION_PATH,
        CODEMETA_PATH,
        CONFORMANCE_RECEIPT_SCHEMA_ID,
        PROJECT_ROOT,
        RESULT_CONTRACT_EXAMPLE_SUFFIXES,
        RESULT_CONTRACT_EXAMPLES_ROOT,
        RESULT_CONTRACT_SCHEMA_ID,
        SDIST_REQUIRED_RELEASE_FILES,
        canonical_readme_relative_files,
        verify_conformance_manifest,
        verify_conformance_receipt_schema,
        verify_golden_core_registry,
        verify_package_index_links,
        verify_release_description,
        verify_result_contract_schema,
    )
    from distribution_artifact_wheel import (
        parse_metadata,
        sha256,
        verify_metadata,
    )


def _launcher_mode(
    members: dict[str, tarfile.TarInfo],
    root: str,
    sdist_name: str,
) -> int:
    launcher_name = f"{root}/qzx.sh"
    launcher = members.get(launcher_name)
    if launcher is None or not launcher.isfile():
        raise ValueError(
            f"{sdist_name} has no regular {launcher_name} launcher."
        )
    mode = launcher.mode & 0o777
    if mode != 0o755:
        raise ValueError(
            f"{sdist_name} stores qzx.sh as {mode:04o}; "
            "release source distributions require 0755."
        )
    return mode


def _result_contract_example_names(root: str) -> set[str]:
    return {
        f"{root}/{path.relative_to(PROJECT_ROOT).as_posix()}"
        for path in sorted(RESULT_CONTRACT_EXAMPLES_ROOT.rglob("*"))
        if path.is_file()
        and (
            path.suffix.lower() in RESULT_CONTRACT_EXAMPLE_SUFFIXES
            or path.name == "mvnw"
        )
    }


def _required_sdist_names(root: str) -> set[str]:
    names = {
        f"{root}/PKG-INFO",
        f"{root}/README.md",
        *(f"{root}/{path}" for path in SDIST_REQUIRED_RELEASE_FILES),
    }
    names.update(_result_contract_example_names(root))
    names.update(
        f"{root}/{relative_path}"
        for relative_path in canonical_readme_relative_files()
    )
    return names


def _require_regular_members(
    members: dict[str, tarfile.TarInfo],
    required_names: set[str],
    sdist_name: str,
) -> dict[str, tarfile.TarInfo]:
    missing = [
        name
        for name in sorted(required_names)
        if (member := members.get(name)) is None or not member.isfile()
    ]
    if missing:
        raise ValueError(
            f"{sdist_name} is missing required release files: "
            + ", ".join(missing)
            + "."
        )
    return {name: members[name] for name in required_names}


def _read_member_text(
    archive: tarfile.TarFile,
    member: tarfile.TarInfo,
    sdist_name: str,
) -> str:
    handle = archive.extractfile(member)
    if handle is None:
        raise ValueError(f"{sdist_name} contains unreadable metadata.")
    return handle.read().decode("utf-8")


def _sdist_payloads(
    archive: tarfile.TarFile,
    members: dict[str, tarfile.TarInfo],
    root: str,
    sdist_name: str,
) -> tuple[dict[str, str], dict[str, str]]:
    required = _require_regular_members(
        members,
        _required_sdist_names(root),
        sdist_name,
    )
    names = {
        "metadata": f"{root}/PKG-INFO",
        "readme": f"{root}/README.md",
        "codemeta": f"{root}/codemeta.json",
        "citation": f"{root}/CITATION.cff",
        "result_schema": (
            f"{root}/src/qzx/resources/schemas/"
            "result-contract-v1.schema.json"
        ),
        "receipt_schema": (
            f"{root}/src/qzx/resources/schemas/"
            "result-contract-conformance-receipt-v1.schema.json"
        ),
        "golden_core": f"{root}/src/qzx/resources/golden-core.json",
        "manifest": f"{root}/examples/result_contract/manifest.json",
    }
    payloads = {
        key: _read_member_text(archive, required[name], sdist_name)
        for key, name in names.items()
    }
    return payloads, names


def _verify_sdist_identity(
    payloads: dict[str, str],
    sdist_name: str,
    *,
    expected_version: str,
    expected_python: str,
) -> None:
    metadata_text = payloads["metadata"]
    verify_metadata(
        parse_metadata(metadata_text, sdist_name),
        expected_version=expected_version,
        expected_python=expected_python,
        context=sdist_name,
    )
    if payloads["codemeta"] != CODEMETA_PATH.read_text(encoding="utf-8"):
        raise ValueError(
            f"{sdist_name} codemeta.json diverges from the repository projection."
        )
    if payloads["citation"] != CITATION_PATH.read_text(encoding="utf-8"):
        raise ValueError(
            f"{sdist_name} CITATION.cff diverges from the repository citation."
        )
    if ATTRIBUTION not in payloads["readme"] or ATTRIBUTION not in metadata_text:
        raise ValueError(f"{sdist_name} does not contain the required attribution.")
    verify_release_description(
        metadata_text,
        expected_version=expected_version,
        context=f"{sdist_name} PKG-INFO",
    )
    verify_package_index_links(metadata_text, f"{sdist_name} PKG-INFO")
    verify_release_description(
        payloads["readme"],
        expected_version=expected_version,
        context=f"{sdist_name} README.md",
    )


def _verify_sdist_contracts(
    payloads: dict[str, str],
    names: dict[str, str],
    sdist_name: str,
) -> tuple[int, int]:
    verify_result_contract_schema(
        payloads["result_schema"],
        f"{sdist_name}:{names['result_schema']}",
    )
    verify_conformance_receipt_schema(
        payloads["receipt_schema"],
        f"{sdist_name}:{names['receipt_schema']}",
    )
    golden_core_commands = verify_golden_core_registry(
        payloads["golden_core"],
        f"{sdist_name}:{names['golden_core']}",
    )
    conformance_cases = verify_conformance_manifest(
        payloads["manifest"],
        f"{sdist_name}:{names['manifest']}",
    )
    return golden_core_commands, conformance_cases


def verify_sdist(
    sdist_path: Path,
    *,
    expected_version: str,
    expected_python: str,
) -> dict[str, object]:
    """Inspect sdist metadata, attribution, release files, and launcher mode."""
    root = f"qzx-{expected_version}"
    with tarfile.open(sdist_path, "r:gz") as archive:
        members = {member.name: member for member in archive.getmembers()}
        launcher_mode = _launcher_mode(members, root, sdist_path.name)
        payloads, names = _sdist_payloads(
            archive,
            members,
            root,
            sdist_path.name,
        )
    _verify_sdist_identity(
        payloads,
        sdist_path.name,
        expected_version=expected_version,
        expected_python=expected_python,
    )
    golden_core_commands, conformance_cases = _verify_sdist_contracts(
        payloads,
        names,
        sdist_path.name,
    )
    return {
        "filename": sdist_path.name,
        "size_bytes": sdist_path.stat().st_size,
        "sha256": sha256(sdist_path),
        "qzx_sh_mode": f"{launcher_mode:04o}",
        "result_contract_schema": RESULT_CONTRACT_SCHEMA_ID,
        "conformance_receipt_schema": CONFORMANCE_RECEIPT_SCHEMA_ID,
        "golden_core_commands": golden_core_commands,
        "result_contract_conformance_cases": conformance_cases,
    }
