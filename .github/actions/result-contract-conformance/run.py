#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Run the QZX Result Contract evidence validator inside a composite action."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

ACTION_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ACTION_ROOT.parents[2]
VALIDATOR = REPOSITORY_ROOT / "scripts" / "validate_result_contract_evidence.py"
SUPPORTED_PROFILES = {
    "core",
    "mcp-2025-06-18",
    "mcp-2025-11-25",
    "mcp-2026-07-28",
}
UNAVAILABLE = "unavailable"


class ActionOutcome(NamedTuple):
    report: str
    conformant: bool
    profile: str
    receipt_schema: str
    contract_schema_sha256: str
    output_schema_mode: str
    failure_kind: str


def clean_input(name: str, *, required: bool = False, default: str = "") -> str:
    value = os.environ.get(name, default).strip()
    if "\n" in value or "\r" in value:
        raise RuntimeError(f"Action input {name} must not contain line breaks.")
    if required and value == "":
        raise RuntimeError(f"Missing required action input: {name}")
    return value


def workspace_path(name: str, *, required: bool = False, default: str = "") -> str:
    """Return one normalized caller-workspace-relative path."""

    value = clean_input(name, required=required, default=default)
    if value == "":
        return ""

    workspace_text = clean_input("GITHUB_WORKSPACE", required=True)
    workspace = Path(workspace_text).resolve()
    candidate = Path(value)
    resolved = candidate.resolve() if candidate.is_absolute() else (workspace / candidate).resolve()
    try:
        relative = resolved.relative_to(workspace)
    except ValueError as exception:
        raise RuntimeError(
            f"Action input {name} must stay inside GITHUB_WORKSPACE."
        ) from exception
    if relative == Path("."):
        raise RuntimeError(f"Action input {name} must identify a file, not the workspace root.")
    return relative.as_posix()


def append_line(path_text: str, text: str) -> None:
    if path_text == "":
        return
    with Path(path_text).open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(text + "\n")


def write_outputs(outcome: ActionOutcome) -> None:
    github_output = os.environ.get("GITHUB_OUTPUT", "")
    values = {
        "report": outcome.report,
        "conformant": "true" if outcome.conformant else "false",
        "profile": outcome.profile,
        "receipt_schema": outcome.receipt_schema,
        "contract_schema_sha256": outcome.contract_schema_sha256,
        "output_schema_mode": outcome.output_schema_mode,
        "failure_kind": outcome.failure_kind,
    }
    for name, value in values.items():
        append_line(github_output, f"{name}={value}")


def write_summary(outcome: ActionOutcome, *, message: str) -> None:
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY", "")
    if summary_path == "":
        return
    lines = [
        "## QZX Result Contract conformance",
        "",
        f"- Status: **{'PASS' if outcome.conformant else 'FAIL'}**",
        f"- Failure kind: `{outcome.failure_kind}`",
        f"- Profile: `{outcome.profile}`",
        f"- Output schema mode: `{outcome.output_schema_mode}`",
        f"- Receipt: `{outcome.report}`",
        f"- Receipt schema: `{outcome.receipt_schema}`",
        f"- Contract schema SHA-256: `{outcome.contract_schema_sha256}`",
        "- Specification: [QZX Result Contract v1](https://qzx.yumbale.com/en/result-contract)",
        "- QZX: created and maintained by [Alejandro Sánchez](https://qzx.yumbale.com/en/alejandro-sanchez)",
        "",
        message,
    ]
    for line in lines:
        append_line(summary_path, line)


def diagnostic_profile() -> str:
    """Return only a known profile value for early-failure diagnostics."""

    value = os.environ.get("INPUT_PROFILE", "core").strip()
    return value if value in SUPPORTED_PROFILES else UNAVAILABLE


def operational_message(exception: BaseException) -> str:
    """Describe an operational failure without reflecting unsafe values."""

    if isinstance(exception, subprocess.TimeoutExpired):
        return "The validator exceeded the 120-second execution limit."
    if isinstance(exception, OSError):
        return "The Action could not start or persist its local validation evidence."
    return str(exception)


def record_operational_failure(exception: BaseException) -> None:
    profile = diagnostic_profile()
    message = operational_message(exception)
    outcome = ActionOutcome(
        report=UNAVAILABLE,
        conformant=False,
        profile=profile,
        receipt_schema=UNAVAILABLE,
        contract_schema_sha256=UNAVAILABLE,
        output_schema_mode=UNAVAILABLE,
        failure_kind="operational",
    )
    try:
        write_outputs(outcome)
    except OSError:
        print("[WARN] Could not write GitHub Action outputs.", file=sys.stderr)
    try:
        write_summary(outcome, message=message)
    except OSError:
        print("[WARN] Could not write the GitHub job summary.", file=sys.stderr)


def main(*, process_runner=subprocess.run) -> int:
    profile = clean_input("INPUT_PROFILE", default="core") or "core"
    if profile not in SUPPORTED_PROFILES:
        supported = ", ".join(sorted(SUPPORTED_PROFILES))
        raise RuntimeError(f"Action input INPUT_PROFILE must be one of: {supported}.")
    success_path = workspace_path("INPUT_SUCCESS", required=True)
    failure_path = workspace_path("INPUT_FAILURE", required=True)
    tool_definition = workspace_path("INPUT_TOOL_DEFINITION")
    report_path = workspace_path(
        "INPUT_REPORT",
        default="qzx-result-contract-conformance.json",
    )

    command = [
        sys.executable,
        str(VALIDATOR),
        "--profile",
        profile,
        "--success",
        success_path,
        "--failure",
        failure_path,
        "--report",
        report_path,
        "--json",
    ]
    if tool_definition:
        command.extend(["--tool-definition", tool_definition])

    workspace = clean_input("GITHUB_WORKSPACE", required=True)
    process = process_runner(
        command,
        cwd=workspace,
        text=True,
        capture_output=True,
        check=False,
        timeout=120,
    )

    if process.stdout:
        sys.stdout.write(process.stdout)
    if process.stderr:
        sys.stderr.write(process.stderr)

    try:
        report = json.loads(process.stdout)
    except json.JSONDecodeError:
        report = {
            "success": False,
            "message": "QZX conformance action could not parse its validator report.",
            "details": {"profile": profile},
        }

    details = report.get("details", {})
    evaluated_profile = str(details.get("profile", profile))
    receipt_schema = str(report.get("receipt_schema", UNAVAILABLE))
    validation_materials = details.get("validation_materials", {})
    contract_material = (
        validation_materials.get("contract_schema", {})
        if isinstance(validation_materials, dict)
        else {}
    )
    contract_schema_sha256 = str(
        contract_material.get("sha256", UNAVAILABLE)
        if isinstance(contract_material, dict)
        else UNAVAILABLE
    )
    cases = details.get("cases", [])
    schema_modes = {
        str(case.get("profile_facts", {}).get("output_schema_mode"))
        for case in cases
        if isinstance(case, dict)
        and case.get("profile_facts", {}).get("output_schema_mode") is not None
    }
    if len(schema_modes) == 1:
        output_schema_mode = next(iter(schema_modes))
    elif len(schema_modes) > 1:
        output_schema_mode = "mixed"
    else:
        output_schema_mode = "not_applicable"

    conformant = report.get("success") is True
    error_code = report.get("error_code")
    failure_kind = (
        "none"
        if conformant
        else "conformance"
        if error_code == "conformance_failed"
        else "operational"
    )
    report_output = (
        report_path
        if receipt_schema != UNAVAILABLE and error_code != "receipt_write_failed"
        else UNAVAILABLE
    )
    outcome = ActionOutcome(
        report=report_output,
        conformant=conformant,
        profile=evaluated_profile,
        receipt_schema=receipt_schema,
        contract_schema_sha256=contract_schema_sha256,
        output_schema_mode=output_schema_mode,
        failure_kind=failure_kind,
    )
    write_outputs(outcome)
    write_summary(
        outcome,
        message=report.get("message", "No validator message was produced."),
    )

    return process.returncode


def run_action(*, process_runner=subprocess.run) -> int:
    try:
        return main(process_runner=process_runner)
    except (RuntimeError, subprocess.TimeoutExpired, OSError) as exception:
        print(f"[FAIL] {operational_message(exception)}", file=sys.stderr)
        record_operational_failure(exception)
        return 2


if __name__ == "__main__":
    raise SystemExit(run_action())
