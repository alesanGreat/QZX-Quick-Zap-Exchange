#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Validate a reviewable QZX Result Contract v1 success/failure evidence pair."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
SCRIPTS_ROOT = PROJECT_ROOT / "scripts"
for import_root in (SOURCE_ROOT, SCRIPTS_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from qzx.core.result_contract import (  # noqa: E402
    RESULT_CONTRACT_SCHEMA_URL,
    RESULT_CONTRACT_VERSION,
    result_contract_violations,
)
from validate_mcp_result_contract import (  # noqa: E402
    MCP_SPECIFICATION_VERSION,
    validate_mcp_profile,
)

REPORT_SCHEMA_VERSION = 1
PROFILE_CORE = "core"
PROFILE_MCP = "mcp-2026-07-28"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile",
        choices=(PROFILE_CORE, PROFILE_MCP),
        default=PROFILE_CORE,
        help="Conformance profile to validate. Defaults to the transport-neutral core.",
    )
    parser.add_argument(
        "--success",
        required=True,
        help="JSON evidence for one completed successful operation.",
    )
    parser.add_argument(
        "--failure",
        required=True,
        help="JSON evidence for one completed failed operation.",
    )
    parser.add_argument(
        "--tool-definition",
        help="MCP tool definition JSON. Required by the MCP profile.",
    )
    parser.add_argument(
        "--report",
        help="Optional path for a deterministic JSON conformance receipt.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the complete machine-readable conformance receipt.",
    )
    return parser.parse_args()


def _read_json(path_text: str) -> tuple[Any | None, str | None, list[str]]:
    path = Path(path_text)
    try:
        raw = path.read_bytes()
    except OSError as exception:
        return None, None, [f"Could not read {path_text}: {exception}"]

    digest = hashlib.sha256(raw).hexdigest()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exception:
        return None, digest, [f"{path_text} is not UTF-8 JSON: {exception}"]

    try:
        return json.loads(text), digest, []
    except json.JSONDecodeError as exception:
        return None, digest, [f"{path_text} is not valid JSON: {exception}"]


def _actual_core_success(document: Any) -> bool | None:
    if not isinstance(document, dict):
        return None
    value = document.get("success")
    return value if isinstance(value, bool) else None


def _mcp_structured_success(document: Any) -> bool | None:
    if not isinstance(document, dict):
        return None
    result = (
        document.get("result")
        if ("jsonrpc" in document or "result" in document)
        else document
    )
    if not isinstance(result, dict):
        return None
    structured = result.get("structuredContent")
    if not isinstance(structured, dict):
        return None
    value = structured.get("success")
    return value if isinstance(value, bool) else None


def _validate_case(
    *,
    name: str,
    path_text: str,
    expected_success: bool,
    profile: str,
    tool_definition: Any | None,
) -> dict[str, Any]:
    document, digest, read_errors = _read_json(path_text)
    violations = list(read_errors)
    warnings: list[str] = []
    facts: dict[str, Any] = {}

    if not read_errors:
        if profile == PROFILE_CORE:
            violations.extend(result_contract_violations(document))
            actual_success = _actual_core_success(document)
        else:
            mcp_violations, warnings, facts = validate_mcp_profile(
                document,
                tool_definition,
            )
            violations.extend(mcp_violations)
            actual_success = _mcp_structured_success(document)

        if actual_success is not expected_success:
            expected_text = "true" if expected_success else "false"
            violations.append(
                f"{name} evidence must represent success={expected_text}."
            )
    else:
        actual_success = None

    return {
        "name": name,
        "file": path_text,
        "sha256": digest,
        "expected_success": expected_success,
        "actual_success": actual_success,
        "conformant": not violations,
        "violations": violations,
        "warnings": warnings,
        "profile_facts": facts,
    }


def validate_evidence(
    *,
    profile: str,
    success_path: str,
    failure_path: str,
    tool_definition_path: str | None = None,
) -> dict[str, Any]:
    """Return one deterministic evidence receipt for a success/failure pair."""

    global_violations: list[str] = []
    global_warnings: list[str] = []
    tool_definition: Any | None = None
    tool_definition_digest: str | None = None

    if profile == PROFILE_MCP:
        if not tool_definition_path:
            global_violations.append(
                "The MCP profile requires --tool-definition so outputSchema is reviewable."
            )
        else:
            (
                tool_definition,
                tool_definition_digest,
                tool_definition_errors,
            ) = _read_json(tool_definition_path)
            global_violations.extend(tool_definition_errors)
    elif tool_definition_path:
        global_warnings.append(
            "--tool-definition is ignored by the transport-neutral core profile."
        )

    cases = [
        _validate_case(
            name="success",
            path_text=success_path,
            expected_success=True,
            profile=profile,
            tool_definition=tool_definition,
        ),
        _validate_case(
            name="failure",
            path_text=failure_path,
            expected_success=False,
            profile=profile,
            tool_definition=tool_definition,
        ),
    ]

    success = not global_violations and all(case["conformant"] for case in cases)
    return {
        "success": success,
        "message": (
            "The evidence pair conforms to QZX Result Contract v1."
            if success
            else "The evidence pair does not conform to QZX Result Contract v1."
        ),
        "warnings": global_warnings,
        "details": {
            "report_schema_version": REPORT_SCHEMA_VERSION,
            "contract_version": f"v{RESULT_CONTRACT_VERSION}",
            "contract_schema": RESULT_CONTRACT_SCHEMA_URL,
            "profile": profile,
            "mcp_specification": (
                MCP_SPECIFICATION_VERSION if profile == PROFILE_MCP else None
            ),
            "tool_definition": (
                {
                    "file": tool_definition_path,
                    "sha256": tool_definition_digest,
                }
                if tool_definition_path
                else None
            ),
            "violations": global_violations,
            "cases": cases,
        },
    }


def _serialize(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    args = parse_args()
    report = validate_evidence(
        profile=args.profile,
        success_path=args.success,
        failure_path=args.failure,
        tool_definition_path=args.tool_definition,
    )
    serialized = _serialize(report)

    if args.report:
        report_path = Path(args.report)
        try:
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(serialized, encoding="utf-8", newline="\n")
        except OSError as exception:
            report["success"] = False
            report["message"] = "The conformance receipt could not be written."
            report["details"]["violations"].append(
                f"Could not write {args.report}: {exception}"
            )
            serialized = _serialize(report)

    if args.json:
        sys.stdout.write(serialized)
    else:
        prefix = "[OK]" if report["success"] else "[FAIL]"
        print(f"{prefix} {report['message']}")
        print(f"  Profile: {report['details']['profile']}")
        for case in report["details"]["cases"]:
            marker = "OK" if case["conformant"] else "FAIL"
            print(f"  [{marker}] {case['name']}: {case['file']}")
            for violation in case["violations"]:
                print(f"    - {violation}")
            for warning in case["warnings"]:
                print(f"    [WARN] {warning}")
        for violation in report["details"]["violations"]:
            print(f"  - {violation}")
        for warning in report["warnings"]:
            print(f"  [WARN] {warning}")
        if args.report:
            print(f"  Receipt: {args.report}")

    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
