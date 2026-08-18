#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Run the QZX Result Contract v1 positive and negative conformance fixtures."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
DEFAULT_MANIFEST = PROJECT_ROOT / "examples" / "result_contract" / "manifest.json"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from qzx.core.result_contract import (  # noqa: E402
    RESULT_CONTRACT_SCHEMA_URL,
    result_contract_violations,
)
from qzx.core.strict_json import (  # noqa: E402
    StrictJsonError,
    load_json_document,
)


def load_json(path: Path, label: str) -> Any:
    """Load one JSON document with a useful source label."""

    try:
        with path.open("r", encoding="utf-8") as handle:
            return load_json_document(handle)
    except (json.JSONDecodeError, StrictJsonError) as exception:
        raise ValueError(f"{label} contains invalid JSON: {exception}") from exception


def _resolve_case_path(manifest_path: Path, relative_name: str) -> Path:
    if Path(relative_name).is_absolute():
        raise ValueError("Conformance case paths must be relative to the manifest.")
    root = manifest_path.parent.resolve()
    candidate = (root / relative_name).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exception:
        raise ValueError(
            f"Conformance case escapes the manifest directory: {relative_name}"
        ) from exception
    if not candidate.is_file():
        raise ValueError(f"Conformance case file was not found: {relative_name}")
    return candidate


def run_conformance(manifest_path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    """Execute every fixture and return one structured conformance report."""

    manifest_path = manifest_path.resolve()
    manifest = load_json(manifest_path, "conformance manifest")
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise ValueError("The conformance manifest must use schema_version 1.")
    if manifest.get("contract") != RESULT_CONTRACT_SCHEMA_URL:
        raise ValueError(
            "The conformance manifest does not identify QZX Result Contract v1."
        )
    cases = manifest.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("The conformance manifest must contain at least one case.")

    seen_ids: set[str] = set()
    case_results: list[dict[str, Any]] = []
    positive_count = 0
    negative_count = 0
    for index, raw_case in enumerate(cases):
        context = f"cases[{index}]"
        if not isinstance(raw_case, dict):
            raise ValueError(f"{context} must be an object.")
        case_id = raw_case.get("id")
        relative_file = raw_case.get("file")
        expected_conformant = raw_case.get("expected_conformant")
        expected_violations = raw_case.get("expected_violations")
        if not isinstance(case_id, str) or case_id.strip() == "":
            raise ValueError(f"{context}.id must be non-empty text.")
        if case_id in seen_ids:
            raise ValueError(f"Conformance case id is duplicated: {case_id}")
        seen_ids.add(case_id)
        if not isinstance(relative_file, str) or relative_file.strip() == "":
            raise ValueError(f"{context}.file must be non-empty text.")
        if not isinstance(expected_conformant, bool):
            raise ValueError(f"{context}.expected_conformant must be boolean.")
        if (
            not isinstance(expected_violations, list)
            or any(not isinstance(item, str) for item in expected_violations)
        ):
            raise ValueError(f"{context}.expected_violations must be a string array.")
        if expected_conformant and expected_violations:
            raise ValueError(
                f"{context} cannot expect violations for a conforming document."
            )

        case_path = _resolve_case_path(manifest_path, relative_file)
        document = load_json(case_path, f"conformance case {case_id}")
        actual_violations = result_contract_violations(document)
        actual_conformant = actual_violations == []
        passed = (
            actual_conformant is expected_conformant
            and actual_violations == expected_violations
        )
        if expected_conformant:
            positive_count += 1
        else:
            negative_count += 1
        case_results.append({
            "id": case_id,
            "file": relative_file,
            "expected_conformant": expected_conformant,
            "actual_conformant": actual_conformant,
            "expected_violations": expected_violations,
            "actual_violations": actual_violations,
            "passed": passed,
        })

    passed_count = sum(1 for case in case_results if case["passed"])
    failed_count = len(case_results) - passed_count
    return {
        "success": failed_count == 0,
        "message": (
            f"QZX Result Contract v1 conformance passed all {passed_count} cases."
            if failed_count == 0
            else (
                "QZX Result Contract v1 conformance failed "
                f"{failed_count} of {len(case_results)} cases."
            )
        ),
        "details": {
            "contract": RESULT_CONTRACT_SCHEMA_URL,
            "manifest": str(manifest_path),
            "case_count": len(case_results),
            "positive_count": positive_count,
            "negative_count": negative_count,
            "passed_count": passed_count,
            "failed_count": failed_count,
            "cases": case_results,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="Conformance manifest to execute.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print one machine-readable conformance report.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = run_conformance(args.manifest)
    except (OSError, ValueError, TypeError, KeyError) as exception:
        result = {
            "success": False,
            "message": "QZX Result Contract conformance could not be completed.",
            "error": str(exception),
            "error_code": "conformance_suite_invalid",
            "details": {
                "contract": RESULT_CONTRACT_SCHEMA_URL,
                "manifest": str(args.manifest),
                "cases": [],
            },
        }

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(("[OK] " if result["success"] else "[FAIL] ") + result["message"])
        for case in result.get("details", {}).get("cases", []):
            status = "PASS" if case.get("passed") else "FAIL"
            print(f"  [{status}] {case.get('id')}: {case.get('file')}")
            if not case.get("passed"):
                print(
                    "    expected violations: "
                    + json.dumps(case.get("expected_violations"), ensure_ascii=False)
                )
                print(
                    "    actual violations: "
                    + json.dumps(case.get("actual_violations"), ensure_ascii=False)
                )
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
