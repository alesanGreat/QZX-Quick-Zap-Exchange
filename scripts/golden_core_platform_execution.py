"""Invoke QZX commands and build sanitized Golden Core evidence records."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from qzx.core.result_contract import result_contract_violations
from scripts.golden_core_platform_assertions import command_assertions
from scripts.golden_core_platform_common import (
    sanitize_text,
    sanitize_value,
    sha256_value,
)


def run_qzx(
    name: str,
    arguments: list[str],
    *,
    cwd: Path,
    replacements: list[tuple[str, str]],
    expected_qzx_command_count=87,
):
    """Run one QZX command and produce its sanitized evidence record."""
    completed, elapsed_ms = _run_process(arguments, cwd)
    document = _validated_document(name, completed)
    sanitized = sanitize_value(document, replacements)
    assertions = command_assertions(
        name,
        sanitized,
        expected_qzx_command_count=expected_qzx_command_count,
    )
    return {
        "arguments": sanitize_value(arguments, replacements),
        "exit_code": completed.returncode,
        "elapsed_ms": elapsed_ms,
        "stderr": sanitize_text(completed.stderr.strip(), replacements),
        "result_sha256": sha256_value(sanitized),
        "assertions": assertions,
        "result": sanitized,
    }


def _run_process(arguments, cwd):
    command = [
        sys.executable,
        "-B",
        "-m",
        "qzx",
        *arguments,
        "--json",
    ]
    environment = dict(os.environ)
    environment["QZX_TELEMETRY"] = "0"
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    started = time.monotonic()
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=90,
    )
    elapsed_ms = round((time.monotonic() - started) * 1000, 3)
    return completed, elapsed_ms


def _validated_document(name, completed):
    if completed.returncode != 0:
        raise RuntimeError(
            f"{name} exited with {completed.returncode}: "
            f"{completed.stderr.strip()}"
        )
    try:
        document = json.loads(completed.stdout)
    except json.JSONDecodeError as exception:
        raise RuntimeError(
            f"{name} did not print one JSON document."
        ) from exception
    if not isinstance(document, dict):
        raise RuntimeError(f"{name} did not print a JSON object.")

    violations = result_contract_violations(document)
    if violations:
        raise RuntimeError(
            f"{name} violated Result Contract v1: {violations}"
        )
    if document.get("success") is not True:
        raise RuntimeError(
            f"{name} reported failure: {document.get('message')}"
        )
    meta = document.get("meta")
    if not isinstance(meta, dict) or meta.get("command") != name:
        raise RuntimeError(
            f"{name} returned the wrong meta.command."
        )
    return document
