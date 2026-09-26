#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Wheel and shared archive validation for QZX distribution candidates."""

from __future__ import annotations

import hashlib
import zipfile
from email.parser import Parser
from pathlib import Path

try:
    from scripts.distribution_artifact_contract import (
        ATTRIBUTION,
        CONFORMANCE_RECEIPT_SCHEMA_ID,
        CONFORMANCE_RECEIPT_WHEEL_PATH,
        GOLDEN_CORE_WHEEL_PATH,
        RESULT_CONTRACT_SCHEMA_ID,
        RESULT_CONTRACT_WHEEL_PATH,
        verify_conformance_receipt_schema,
        verify_golden_core_registry,
        verify_package_index_links,
        verify_release_description,
        verify_result_contract_schema,
    )
except ModuleNotFoundError:
    from distribution_artifact_contract import (
        ATTRIBUTION,
        CONFORMANCE_RECEIPT_SCHEMA_ID,
        CONFORMANCE_RECEIPT_WHEEL_PATH,
        GOLDEN_CORE_WHEEL_PATH,
        RESULT_CONTRACT_SCHEMA_ID,
        RESULT_CONTRACT_WHEEL_PATH,
        verify_conformance_receipt_schema,
        verify_golden_core_registry,
        verify_package_index_links,
        verify_release_description,
        verify_result_contract_schema,
    )


def sha256(path: Path) -> str:
    """Return the hexadecimal SHA-256 digest of one artifact."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


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


def _wheel_payloads(wheel_path: Path) -> dict[str, str]:
    with zipfile.ZipFile(wheel_path) as archive:
        names = set(archive.namelist())
        metadata_names = [
            name for name in names if name.endswith(".dist-info/METADATA")
        ]
        if len(metadata_names) != 1:
            raise ValueError(
                f"{wheel_path.name} must contain exactly one METADATA file."
            )
        resources = (
            RESULT_CONTRACT_WHEEL_PATH,
            CONFORMANCE_RECEIPT_WHEEL_PATH,
            GOLDEN_CORE_WHEEL_PATH,
        )
        missing = [name for name in resources if name not in names]
        if missing:
            raise ValueError(
                f"{wheel_path.name} is missing packaged resources: "
                + ", ".join(missing)
                + "."
            )
        return {
            "metadata": archive.read(metadata_names[0]).decode("utf-8"),
            "result_schema": archive.read(
                RESULT_CONTRACT_WHEEL_PATH
            ).decode("utf-8"),
            "receipt_schema": archive.read(
                CONFORMANCE_RECEIPT_WHEEL_PATH
            ).decode("utf-8"),
            "golden_core": archive.read(GOLDEN_CORE_WHEEL_PATH).decode("utf-8"),
        }


def verify_wheel(
    wheel_path: Path,
    *,
    expected_version: str,
    expected_python: str,
) -> dict[str, object]:
    """Inspect the wheel metadata and packaged long description."""
    payloads = _wheel_payloads(wheel_path)
    metadata_text = payloads["metadata"]
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
        payloads["result_schema"],
        f"{wheel_path.name}:{RESULT_CONTRACT_WHEEL_PATH}",
    )
    verify_conformance_receipt_schema(
        payloads["receipt_schema"],
        f"{wheel_path.name}:{CONFORMANCE_RECEIPT_WHEEL_PATH}",
    )
    golden_core_commands = verify_golden_core_registry(
        payloads["golden_core"],
        f"{wheel_path.name}:{GOLDEN_CORE_WHEEL_PATH}",
    )
    return {
        "filename": wheel_path.name,
        "size_bytes": wheel_path.stat().st_size,
        "sha256": sha256(wheel_path),
        "result_contract_schema": RESULT_CONTRACT_SCHEMA_ID,
        "conformance_receipt_schema": CONFORMANCE_RECEIPT_SCHEMA_ID,
        "golden_core_commands": golden_core_commands,
    }
