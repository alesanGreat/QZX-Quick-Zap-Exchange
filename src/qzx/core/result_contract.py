#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""QZX Result Contract v1 validation without third-party dependencies."""

from __future__ import annotations

import json
import math
import re
from importlib.resources import files
from typing import Any


RESULT_CONTRACT_VERSION = 1
RESULT_CONTRACT_SCHEMA_URL = (
    "https://qzx.yumbale.com/schemas/result-contract-v1.schema.json"
)
_RESULT_CONTRACT_RESOURCE = "schemas/result-contract-v1.schema.json"
_ERROR_CODE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


def load_result_contract_schema() -> dict[str, Any]:
    """Return the packaged JSON Schema for QZX Result Contract v1."""

    schema_path = files("qzx.resources").joinpath(_RESULT_CONTRACT_RESOURCE)
    with schema_path.open("r", encoding="utf-8") as handle:
        schema = json.load(handle)
    if not isinstance(schema, dict):
        raise RuntimeError("The packaged QZX result-contract schema is invalid.")
    return schema


def result_contract_violations(document: Any) -> list[str]:
    """Return stable, human-readable violations of the v1 core envelope."""

    violations: list[str] = []
    if not isinstance(document, dict):
        return ["The result must be a JSON object."]

    success = document.get("success")
    if not isinstance(success, bool):
        violations.append("success must be a boolean.")

    message = document.get("message")
    if not isinstance(message, str) or message.strip() == "":
        violations.append("message must be a non-empty string.")

    error = document.get("error")
    if error is not None and (
        not isinstance(error, str) or error.strip() == ""
    ):
        violations.append("error must be a non-empty string when present.")

    error_code = document.get("error_code")
    if error_code is not None and (
        not isinstance(error_code, str)
        or _ERROR_CODE_PATTERN.fullmatch(error_code) is None
    ):
        violations.append(
            "error_code must use lower_snake_case when present."
        )

    if success is False and error is None and error_code is None:
        violations.append(
            "A failed result must include error or error_code."
        )

    details = document.get("details")
    if details is not None and not isinstance(details, dict):
        violations.append("details must be an object when present.")

    warnings = document.get("warnings")
    if warnings is not None:
        if not isinstance(warnings, list):
            violations.append("warnings must be an array when present.")
        elif any(
            not isinstance(item, str) or item.strip() == ""
            for item in warnings
        ):
            violations.append(
                "Every warnings item must be a non-empty string."
            )

    meta = document.get("meta")
    if meta is not None:
        if not isinstance(meta, dict):
            violations.append("meta must be an object when present.")
        else:
            schema_version = meta.get("schema_version")
            if schema_version is not None and (
                isinstance(schema_version, bool)
                or schema_version != RESULT_CONTRACT_VERSION
            ):
                violations.append("meta.schema_version must equal 1.")

            command = meta.get("command")
            if command is not None and (
                not isinstance(command, str) or command.strip() == ""
            ):
                violations.append(
                    "meta.command must be a non-empty string when present."
                )

            duration_ms = meta.get("duration_ms")
            if duration_ms is not None and (
                isinstance(duration_ms, bool)
                or not isinstance(duration_ms, (int, float))
                or not math.isfinite(duration_ms)
                or duration_ms < 0
            ):
                violations.append(
                    "meta.duration_ms must be a finite non-negative number."
                )

            maturity = meta.get("command_maturity")
            if maturity is not None and not isinstance(maturity, dict):
                violations.append(
                    "meta.command_maturity must be an object when present."
                )

    return violations


def ensure_result_contract(document: Any) -> dict[str, Any]:
    """Return a conforming result, replacing invalid producer output safely."""

    violations = result_contract_violations(document)
    if not violations:
        return document

    return {
        "success": False,
        "message": (
            "QZX rejected an internal result that violated "
            "QZX Result Contract v1."
        ),
        "error": "; ".join(violations),
        "error_code": "invalid_result_contract",
        "details": {
            "violations": violations,
            "contract": RESULT_CONTRACT_SCHEMA_URL,
        },
        "meta": {
            "schema_version": RESULT_CONTRACT_VERSION,
        },
    }
