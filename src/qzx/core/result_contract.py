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

    has_error = "error" in document
    error = document.get("error")
    if has_error and (
        not isinstance(error, str) or error.strip() == ""
    ):
        violations.append("error must be a non-empty string when present.")

    has_error_code = "error_code" in document
    error_code = document.get("error_code")
    if has_error_code and (
        not isinstance(error_code, str)
        or _ERROR_CODE_PATTERN.fullmatch(error_code) is None
    ):
        violations.append(
            "error_code must use lower_snake_case when present."
        )

    if success is False and not has_error and not has_error_code:
        violations.append(
            "A failed result must include error or error_code."
        )
    if success is True and (has_error or has_error_code):
        violations.append(
            "A successful result must not include error or error_code."
        )

    if "details" in document and not isinstance(document["details"], dict):
        violations.append("details must be an object when present.")

    if "warnings" in document:
        warnings = document["warnings"]
        if not isinstance(warnings, list):
            violations.append("warnings must be an array when present.")
        elif any(
            not isinstance(item, str) or item.strip() == ""
            for item in warnings
        ):
            violations.append(
                "Every warnings item must be a non-empty string."
            )

    if "meta" in document:
        meta = document["meta"]
        if not isinstance(meta, dict):
            violations.append("meta must be an object when present.")
        else:
            if "schema_version" in meta:
                schema_version = meta["schema_version"]
                if (
                    isinstance(schema_version, bool)
                    or schema_version != RESULT_CONTRACT_VERSION
                ):
                    violations.append("meta.schema_version must equal 1.")

            if "command" in meta:
                command = meta["command"]
                if not isinstance(command, str) or command.strip() == "":
                    violations.append(
                        "meta.command must be a non-empty string when present."
                    )

            if "duration_ms" in meta:
                duration_ms = meta["duration_ms"]
                if (
                    isinstance(duration_ms, bool)
                    or not isinstance(duration_ms, (int, float))
                    or not math.isfinite(duration_ms)
                    or duration_ms < 0
                ):
                    violations.append(
                        "meta.duration_ms must be a finite non-negative number."
                    )

            if "command_maturity" in meta:
                maturity = meta["command_maturity"]
                if not isinstance(maturity, dict):
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
