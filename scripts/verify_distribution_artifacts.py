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
        metadata_names = [
            name
            for name in archive.namelist()
            if name.endswith(".dist-info/METADATA")
        ]
        if len(metadata_names) != 1:
            raise ValueError(
                f"{wheel_path.name} must contain exactly one METADATA file."
            )
        metadata_text = archive.read(metadata_names[0]).decode("utf-8")

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
    return {
        "filename": wheel_path.name,
        "size_bytes": wheel_path.stat().st_size,
        "sha256": sha256(wheel_path),
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
        if metadata_member is None or readme_member is None:
            raise ValueError(
                f"{sdist_path.name} must contain PKG-INFO and README.md."
            )
        metadata_handle = archive.extractfile(metadata_member)
        readme_handle = archive.extractfile(readme_member)
        if metadata_handle is None or readme_handle is None:
            raise ValueError(f"{sdist_path.name} contains unreadable metadata.")
        metadata_text = metadata_handle.read().decode("utf-8")
        readme_text = readme_handle.read().decode("utf-8")

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
    return {
        "filename": sdist_path.name,
        "size_bytes": sdist_path.stat().st_size,
        "sha256": sha256(sdist_path),
        "qzx_sh_mode": f"{launcher_mode:04o}",
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
