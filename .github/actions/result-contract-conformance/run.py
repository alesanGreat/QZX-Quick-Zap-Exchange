#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Run the QZX Result Contract evidence validator inside a composite action."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ACTION_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ACTION_ROOT.parents[2]
VALIDATOR = REPOSITORY_ROOT / "scripts" / "validate_result_contract_evidence.py"


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


def main() -> int:
    profile = clean_input("INPUT_PROFILE", default="core") or "core"
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
    process = subprocess.run(
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

    append_line(os.environ.get("GITHUB_OUTPUT", ""), f"report={report_path}")

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY", "")
    if summary_path:
        status = "PASS" if report.get("success") else "FAIL"
        lines = [
            "## QZX Result Contract conformance",
            "",
            f"- Status: **{status}**",
            f"- Profile: `{report.get('details', {}).get('profile', profile)}`",
            f"- Receipt: `{report_path}`",
            "",
            report.get("message", "No validator message was produced."),
        ]
        for line in lines:
            append_line(summary_path, line)

    return process.returncode


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exception:
        print(f"[FAIL] {exception}", file=sys.stderr)
        raise SystemExit(2)
