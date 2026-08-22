#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Validate a reviewable QZX Result Contract v1 success/failure evidence pair."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
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
from validate_mcp_result_contract import validate_mcp_profile  # noqa: E402

REPORT_SCHEMA_VERSION = 1
CONFORMANCE_RECEIPT_SCHEMA_URL = (
    "https://qzx.yumbale.com/schemas/"
    "result-contract-conformance-receipt-v1.schema.json"
)
PROFILE_CORE = "core"
MCP_PROFILE_TO_SPECIFICATION = {
    "mcp-2025-06-18": "2025-06-18",
    "mcp-2025-11-25": "2025-11-25",
    "mcp-2026-07-28": "2026-07-28",
}
MCP_PROFILES = tuple(MCP_PROFILE_TO_SPECIFICATION)
PROFILE_MCP = "mcp-2026-07-28"
VALIDATION_MATERIAL_PATHS = {
    "contract_schema": "src/qzx/resources/schemas/result-contract-v1.schema.json",
    "receipt_schema": (
        "src/qzx/resources/schemas/"
        "result-contract-conformance-receipt-v1.schema.json"
    ),
    "core_validator": "src/qzx/core/result_contract.py",
    "mcp_validator": "scripts/validate_mcp_result_contract.py",
    "evidence_validator": "scripts/validate_result_contract_evidence.py",
}


def _validation_materials() -> dict[str, dict[str, str]]:
    """Identify the exact QZX artifacts used to produce a conformance receipt."""

    materials: dict[str, dict[str, str]] = {}
    for name, repository_path in VALIDATION_MATERIAL_PATHS.items():
        raw = (PROJECT_ROOT / repository_path).read_bytes()
        materials[name] = {
            "repository_path": repository_path,
            "sha256": hashlib.sha256(raw).hexdigest(),
        }
    return materials


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile",
        choices=(PROFILE_CORE, *MCP_PROFILES),
        default=PROFILE_CORE,
        help=(
            "Conformance profile to validate. Defaults to the transport-neutral "
            "core. MCP profiles are revision-specific."
        ),
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
        help="MCP tool definition JSON. Required by every MCP profile.",
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
                MCP_PROFILE_TO_SPECIFICATION[profile],
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

    if profile != PROFILE_CORE and profile not in MCP_PROFILE_TO_SPECIFICATION:
        raise ValueError(f"Unsupported QZX Result Contract profile: {profile}")

    global_violations: list[str] = []
    global_warnings: list[str] = []
    tool_definition: Any | None = None
    tool_definition_digest: str | None = None

    if profile in MCP_PROFILE_TO_SPECIFICATION:
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
        "receipt_schema": CONFORMANCE_RECEIPT_SCHEMA_URL,
        "success": success,
        "message": (
            "The evidence pair conforms to QZX Result Contract v1."
            if success
            else "The evidence pair does not conform to QZX Result Contract v1."
        ),
        **({"error_code": "conformance_failed"} if not success else {}),
        "warnings": global_warnings,
        "details": {
            "report_schema_version": REPORT_SCHEMA_VERSION,
            "contract_version": f"v{RESULT_CONTRACT_VERSION}",
            "contract_schema": RESULT_CONTRACT_SCHEMA_URL,
            "validation_materials": _validation_materials(),
            "profile": profile,
            "mcp_specification": MCP_PROFILE_TO_SPECIFICATION.get(profile),
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


def _path_identities(path_text: str) -> set[str]:
    """Return lexical and resolvable identities without requiring a valid target."""

    path = Path(path_text)
    identities = {
        os.path.normcase(os.path.abspath(os.path.normpath(os.fspath(path))))
    }
    try:
        identities.add(os.path.normcase(str(path.resolve(strict=False))))
    except (OSError, RuntimeError):
        # Broken links and symlink loops remain safe through lexical comparison
        # plus atomic replacement; they must not crash receipt generation.
        pass
    return identities


def _write_text_atomic(
    path: Path,
    content: str,
    *,
    replace_file=None,
) -> None:
    """Replace one receipt atomically without following the destination link."""

    if replace_file is None:
        replace_file = os.replace
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(
            descriptor,
            mode="w",
            encoding="utf-8",
            newline="\n",
        ) as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        replace_file(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def _conflicting_evidence_role(
    report_path: str,
    *,
    success_path: str,
    failure_path: str,
    tool_definition_path: str | None,
) -> str | None:
    """Return the evidence role that a receipt would overwrite, if any."""

    report = Path(report_path)
    report_identities = _path_identities(report_path)
    evidence_paths = {
        "success": success_path,
        "failure": failure_path,
        "tool definition": tool_definition_path,
    }
    for role, path_text in evidence_paths.items():
        if path_text is None:
            continue
        evidence = Path(path_text)
        if report_identities & _path_identities(path_text):
            return role
        try:
            if (
                os.path.lexists(report)
                and os.path.lexists(evidence)
                and report.samefile(evidence)
            ):
                return role
        except OSError:
            # Normalized-path comparison still protects aliases that can be
            # resolved even when the platform cannot query file identity.
            pass
    return None


def main() -> int:
    args = parse_args()
    report = validate_evidence(
        profile=args.profile,
        success_path=args.success,
        failure_path=args.failure,
        tool_definition_path=args.tool_definition,
    )
    conflicting_role = (
        _conflicting_evidence_role(
            args.report,
            success_path=args.success,
            failure_path=args.failure,
            tool_definition_path=args.tool_definition,
        )
        if args.report
        else None
    )
    if conflicting_role is not None:
        report["success"] = False
        report["message"] = (
            "The conformance receipt path conflicts with an evidence input."
        )
        report["error_code"] = "receipt_path_conflict"
        report["details"]["violations"].append(
            "The report path must differ from the "
            f"{conflicting_role} evidence path; no receipt was written."
        )
    serialized = _serialize(report)

    if args.report and conflicting_role is None:
        report_path = Path(args.report)
        try:
            _write_text_atomic(report_path, serialized)
        except OSError as exception:
            report["success"] = False
            report["message"] = "The conformance receipt could not be written."
            report["error_code"] = "receipt_write_failed"
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
