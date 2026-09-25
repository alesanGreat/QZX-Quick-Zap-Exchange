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
    if not isinstance(document, dict):
        return ["The result must be a JSON object."]

    violations: list[str] = []
    _validate_required_fields(document, violations)
    _validate_failure_fields(document, violations)
    _validate_optional_details(document, violations)
    _validate_warnings(document, violations)
    _validate_meta(document, violations)
    return violations


def _validate_required_fields(document: dict[str, Any], violations: list[str]) -> None:
    """Validate the two fields required by every result envelope."""

    success = document.get("success")
    if not isinstance(success, bool):
        violations.append("success must be a boolean.")

    message = document.get("message")
    if not isinstance(message, str) or message.strip() == "":
        violations.append("message must be a non-empty string.")


def _validate_failure_fields(document: dict[str, Any], violations: list[str]) -> None:
    """Validate failure details and their relationship to success."""
    success = document.get("success")
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


def _validate_optional_details(document: dict[str, Any], violations: list[str]) -> None:
    """Require the optional domain-details container to remain an object."""
    if "details" in document and not isinstance(document["details"], dict):
        violations.append("details must be an object when present.")


def _validate_warnings(document: dict[str, Any], violations: list[str]) -> None:
    """Validate optional human-readable warnings."""
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


def _validate_meta(document: dict[str, Any], violations: list[str]) -> None:
    """Validate shared execution metadata without restricting extensions."""
    if "meta" not in document:
        return
    meta = document["meta"]
    if not isinstance(meta, dict):
        violations.append("meta must be an object when present.")
        return
    _validate_meta_schema(meta, violations)
    _validate_meta_command(meta, violations)
    _validate_meta_duration(meta, violations)
    if "command_maturity" in meta and not isinstance(meta["command_maturity"], dict):
        violations.append("meta.command_maturity must be an object when present.")


def _validate_meta_schema(meta: dict[str, Any], violations: list[str]) -> None:
    if "schema_version" not in meta:
        return
    value = meta["schema_version"]
    if isinstance(value, bool) or value != RESULT_CONTRACT_VERSION:
        violations.append("meta.schema_version must equal 1.")


def _validate_meta_command(meta: dict[str, Any], violations: list[str]) -> None:
    if "command" not in meta:
        return
    command = meta["command"]
    if not isinstance(command, str) or command.strip() == "":
        violations.append("meta.command must be a non-empty string when present.")


def _validate_meta_duration(meta: dict[str, Any], violations: list[str]) -> None:
    if "duration_ms" not in meta:
        return
    duration = meta["duration_ms"]
    invalid = (
        isinstance(duration, bool)
        or not isinstance(duration, (int, float))
        or not math.isfinite(duration)
        or duration < 0
    )
    if invalid:
        violations.append("meta.duration_ms must be a finite non-negative number.")


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
