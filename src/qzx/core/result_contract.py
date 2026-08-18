#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""QZX Result Contract v1 validation without third-party dependencies."""

from __future__ import annotations

import json
import math
import re
from importlib.resources import files
from typing import Any, BinaryIO, TextIO


RESULT_CONTRACT_VERSION = 1
RESULT_CONTRACT_SCHEMA_URL = (
    "https://qzx.yumbale.com/schemas/result-contract-v1.schema.json"
)
_RESULT_CONTRACT_RESOURCE = "schemas/result-contract-v1.schema.json"
_ERROR_CODE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


class JsonInteroperabilityError(ValueError):
    """Describe valid-for-some-parsers input that is not portable JSON."""

    def __init__(self, violations: list[str]) -> None:
        self.violations = tuple(violations)
        super().__init__(" ".join(violations))


def loads_interoperable_json(text: str, *, source: str) -> Any:
    """Decode JSON while rejecting ambiguous or non-standard representations."""

    if text.startswith("\ufeff"):
        text = text[1:]

    duplicate_names: set[str] = set()
    non_finite_numbers: set[str] = set()

    def object_with_unique_names(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        parsed: dict[str, Any] = {}
        for name, value in pairs:
            if name in parsed:
                duplicate_names.add(name)
            parsed[name] = value
        return parsed

    def record_non_finite_number(value: str) -> None:
        non_finite_numbers.add(value)

    try:
        document = json.loads(
            text,
            object_pairs_hook=object_with_unique_names,
            parse_constant=record_non_finite_number,
        )
    except RecursionError as exception:
        raise JsonInteroperabilityError(
            [f"{source} exceeds the supported JSON nesting depth."]
        ) from exception

    violations: list[str] = []
    if duplicate_names:
        rendered_names = ", ".join(
            json.dumps(name, ensure_ascii=True) for name in sorted(duplicate_names)
        )
        violations.append(
            f"{source} contains duplicate JSON object member names: "
            f"{rendered_names}."
        )
    if non_finite_numbers:
        rendered_numbers = ", ".join(sorted(non_finite_numbers))
        violations.append(
            f"{source} contains non-finite numeric tokens that JSON does not "
            f"permit: {rendered_numbers}."
        )
    if _contains_unpaired_surrogate(document):
        violations.append(
            f"{source} contains an unpaired UTF-16 surrogate; its cross-parser "
            "behavior is unpredictable."
        )

    if violations:
        raise JsonInteroperabilityError(violations)
    return document


def loads_interoperable_json_bytes(data: bytes, *, source: str) -> Any:
    """Decode RFC 8259 JSON bytes as UTF-8 before enforcing portability."""

    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exception:
        raise JsonInteroperabilityError(
            [f"{source} is not valid UTF-8 at byte offset {exception.start}."]
        ) from exception
    return loads_interoperable_json(text, source=source)


def _contains_unpaired_surrogate(document: Any) -> bool:
    """Inspect decoded JSON iteratively so deeply nested data cannot recurse."""

    pending = [document]
    while pending:
        value = pending.pop()
        if isinstance(value, str):
            if any("\ud800" <= character <= "\udfff" for character in value):
                return True
        elif isinstance(value, dict):
            pending.extend(value.keys())
            pending.extend(value.values())
        elif isinstance(value, list):
            pending.extend(value)
    return False


def load_interoperable_json(
    handle: TextIO | BinaryIO,
    *,
    source: str,
) -> Any:
    """Decode one interoperable JSON document from a text or binary stream."""

    content = handle.read()
    if isinstance(content, bytes):
        return loads_interoperable_json_bytes(content, source=source)
    return loads_interoperable_json(content, source=source)


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
