#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Verify QZX wheel and source-distribution release contracts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

if __package__:
    from .distribution_artifact_contract import (  # noqa: E402
        ATTRIBUTION,
        CITATION_PATH,
        CODEMETA_PATH,
        CONFORMANCE_RECEIPT_SCHEMA_ID,
        CONFORMANCE_RECEIPT_WHEEL_PATH,
        DISTRIBUTION_VERIFIER_SUPPORT_FILES,
        GOLDEN_CORE_WHEEL_PATH,
        PRODUCT_MANIFEST_PATH,
        PROJECT_ROOT,
        README_PATH,
        RESULT_CONTRACT_EXAMPLE_SUFFIXES,
        RESULT_CONTRACT_EXAMPLES_ROOT,
        RESULT_CONTRACT_MANIFEST_PATH,
        RESULT_CONTRACT_SCHEMA_ID,
        SDIST_FORBIDDEN_PRIVATE_FILES,
        RESULT_CONTRACT_WHEEL_PATH,
        canonical_readme_relative_files,
        find_repository_relative_links,
        is_repository_relative_destination,
        load_canonical_conformance_manifest,
        release_readme_marker,
        render_package_readme,
        verify_conformance_manifest,
        verify_conformance_receipt_schema,
        verify_golden_core_registry,
        verify_package_index_links,
        verify_release_description,
        verify_result_contract_schema,
    )
    from .distribution_artifact_sdist import verify_sdist  # noqa: E402
    from .distribution_artifact_wheel import (  # noqa: E402
        parse_metadata,
        require_single_artifact,
        sha256,
        verify_metadata,
        verify_wheel,
    )
else:
    import sys

    _SCRIPTS_ROOT = str(Path(__file__).resolve().parent)
    if _SCRIPTS_ROOT not in sys.path:
        sys.path.insert(0, _SCRIPTS_ROOT)
    from distribution_artifact_contract import (  # noqa: E402
        ATTRIBUTION,
        CITATION_PATH,
        CODEMETA_PATH,
        CONFORMANCE_RECEIPT_SCHEMA_ID,
        CONFORMANCE_RECEIPT_WHEEL_PATH,
        DISTRIBUTION_VERIFIER_SUPPORT_FILES,
        GOLDEN_CORE_WHEEL_PATH,
        PRODUCT_MANIFEST_PATH,
        PROJECT_ROOT,
        README_PATH,
        RESULT_CONTRACT_EXAMPLE_SUFFIXES,
        RESULT_CONTRACT_EXAMPLES_ROOT,
        RESULT_CONTRACT_MANIFEST_PATH,
        RESULT_CONTRACT_SCHEMA_ID,
        SDIST_FORBIDDEN_PRIVATE_FILES,
        RESULT_CONTRACT_WHEEL_PATH,
        canonical_readme_relative_files,
        find_repository_relative_links,
        is_repository_relative_destination,
        load_canonical_conformance_manifest,
        release_readme_marker,
        render_package_readme,
        verify_conformance_manifest,
        verify_conformance_receipt_schema,
        verify_golden_core_registry,
        verify_package_index_links,
        verify_release_description,
        verify_result_contract_schema,
    )
    from distribution_artifact_sdist import verify_sdist  # noqa: E402
    from distribution_artifact_wheel import (  # noqa: E402
        parse_metadata,
        require_single_artifact,
        sha256,
        verify_metadata,
        verify_wheel,
    )


__all__ = [
    "ATTRIBUTION",
    "CITATION_PATH",
    "CODEMETA_PATH",
    "CONFORMANCE_RECEIPT_SCHEMA_ID",
    "CONFORMANCE_RECEIPT_WHEEL_PATH",
    "DISTRIBUTION_VERIFIER_SUPPORT_FILES",
    "GOLDEN_CORE_WHEEL_PATH",
    "PRODUCT_MANIFEST_PATH",
    "PROJECT_ROOT",
    "README_PATH",
    "RESULT_CONTRACT_EXAMPLE_SUFFIXES",
    "RESULT_CONTRACT_EXAMPLES_ROOT",
    "RESULT_CONTRACT_MANIFEST_PATH",
    "RESULT_CONTRACT_SCHEMA_ID",
    "SDIST_FORBIDDEN_PRIVATE_FILES",
    "RESULT_CONTRACT_WHEEL_PATH",
    "canonical_readme_relative_files",
    "find_repository_relative_links",
    "is_repository_relative_destination",
    "load_canonical_conformance_manifest",
    "release_readme_marker",
    "render_package_readme",
    "verify_conformance_manifest",
    "verify_conformance_receipt_schema",
    "verify_golden_core_registry",
    "verify_package_index_links",
    "verify_release_description",
    "verify_result_contract_schema",
    "parse_metadata",
    "require_single_artifact",
    "sha256",
    "verify_metadata",
    "verify_wheel",
    "verify_sdist",
]


def load_release_contract() -> tuple[str, str]:
    """Read the candidate version and Python requirement from one source."""
    with PRODUCT_MANIFEST_PATH.open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    development = manifest["channels"]["development"]
    return development["version"], development["requires_python"]


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
        "message": f"Verified QZX {expected_version} wheel and source distribution.",
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
