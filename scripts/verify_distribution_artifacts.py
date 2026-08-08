#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Verify QZX wheel and source-distribution release contracts."""

from __future__ import annotations

import argparse
import hashlib
import json
import tarfile
import zipfile
from email.parser import Parser
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PRODUCT_MANIFEST_PATH = (
    PROJECT_ROOT / "src" / "qzx" / "resources" / "product-manifest.json"
)
ATTRIBUTION = (
    "QZX — Quick Zap Exchange, created and maintained by Alejandro Sánchez."
)
RESULT_CONTRACT_SCHEMA_ID = (
    "https://qzx.yumbale.com/schemas/result-contract-v1.schema.json"
)
RESULT_CONTRACT_WHEEL_PATH = (
    "qzx/resources/schemas/result-contract-v1.schema.json"
)


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
        if RESULT_CONTRACT_WHEEL_PATH not in names:
            raise ValueError(
                f"{wheel_path.name} does not contain "
                f"{RESULT_CONTRACT_WHEEL_PATH}."
            )
        metadata_text = archive.read(metadata_names[0]).decode("utf-8")
        result_contract_schema = archive.read(
            RESULT_CONTRACT_WHEEL_PATH
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
    verify_result_contract_schema(
        result_contract_schema,
        f"{wheel_path.name}:{RESULT_CONTRACT_WHEEL_PATH}",
    )
    return {
        "filename": wheel_path.name,
        "size_bytes": wheel_path.stat().st_size,
        "sha256": sha256(wheel_path),
        "result_contract_schema": RESULT_CONTRACT_SCHEMA_ID,
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
        schema_name = (
            f"{root}/src/qzx/resources/schemas/"
            "result-contract-v1.schema.json"
        )
        specification_name = f"{root}/docs/result-contract-v1.md"
        validator_name = f"{root}/scripts/validate_result_contract.py"
        required_members = {
            "PKG-INFO": metadata_member,
            "README.md": readme_member,
            schema_name: members.get(schema_name),
            specification_name: members.get(specification_name),
            validator_name: members.get(validator_name),
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
        schema_handle = archive.extractfile(required_members[schema_name])
        if (
            metadata_handle is None
            or readme_handle is None
            or schema_handle is None
        ):
            raise ValueError(f"{sdist_path.name} contains unreadable metadata.")
        metadata_text = metadata_handle.read().decode("utf-8")
        readme_text = readme_handle.read().decode("utf-8")
        result_contract_schema = schema_handle.read().decode("utf-8")

    verify_metadata(
        parse_metadata(metadata_text, sdist_path.name),
        expected_version=expected_version,
        expected_python=expected_python,
        context=sdist_path.name,
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
    verify_release_description(
        readme_text,
        expected_version=expected_version,
        context=f"{sdist_path.name} README.md",
    )
    verify_result_contract_schema(
        result_contract_schema,
        f"{sdist_path.name}:{schema_name}",
    )
    return {
        "filename": sdist_path.name,
        "size_bytes": sdist_path.stat().st_size,
        "sha256": sha256(sdist_path),
        "qzx_sh_mode": f"{launcher_mode:04o}",
        "result_contract_schema": RESULT_CONTRACT_SCHEMA_ID,
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
