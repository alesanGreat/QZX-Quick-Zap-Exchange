#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Strict RFC 8259 JSON decoding for interoperable evidence."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, BinaryIO, TextIO


class StrictJsonError(ValueError):
    """Raised when valid-looking input is not interoperable RFC 8259 JSON."""


_MAX_JSON_NESTING_DEPTH = 512


def _object_with_unique_names(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, value in pairs:
        if name in result:
            encoded_name = json.dumps(name, ensure_ascii=True)
            raise StrictJsonError(
                f"Duplicate JSON object member name: {encoded_name}."
            )
        result[name] = value
    return result


def _finite_float(token: str) -> float:
    value = float(token)
    if not math.isfinite(value):
        raise StrictJsonError(
            f"JSON number is outside the supported finite range: {token}."
        )
    return value


def _reject_non_json_constant(token: str) -> None:
    raise StrictJsonError(f"JSON does not permit the numeric token {token}.")


def _string_has_unpaired_surrogate(value: str) -> bool:
    index = 0
    while index < len(value):
        codepoint = ord(value[index])
        if 0xD800 <= codepoint <= 0xDBFF:
            if index + 1 >= len(value):
                return True
            following = ord(value[index + 1])
            if not 0xDC00 <= following <= 0xDFFF:
                return True
            index += 2
            continue
        if 0xDC00 <= codepoint <= 0xDFFF:
            return True
        index += 1
    return False


def _validate_decoded_document(document: Any) -> None:
    """Reject non-portable Unicode and excessive structural nesting."""

    pending = [(document, 0)]
    while pending:
        value, depth = pending.pop()
        if isinstance(value, str):
            if _string_has_unpaired_surrogate(value):
                raise StrictJsonError(
                    "JSON document contains an unpaired UTF-16 surrogate."
                )
            continue
        if not isinstance(value, (dict, list)):
            continue

        nested_depth = depth + 1
        if nested_depth > _MAX_JSON_NESTING_DEPTH:
            raise StrictJsonError(
                "JSON document exceeds the supported nesting depth."
            )

        if isinstance(value, dict):
            pending.extend((key, nested_depth) for key in value)
            pending.extend((item, nested_depth) for item in value.values())
        else:
            pending.extend((item, nested_depth) for item in value)


def loads_json_document(text: str) -> Any:
    """Decode one RFC 8259 document from text with strict evidence rules."""

    if text.startswith("\ufeff"):
        text = text[1:]
    try:
        document = json.loads(
            text,
            object_pairs_hook=_object_with_unique_names,
            parse_constant=_reject_non_json_constant,
            parse_float=_finite_float,
        )
    except RecursionError as exception:
        raise StrictJsonError(
            "JSON document exceeds the supported nesting depth."
        ) from exception
    _validate_decoded_document(document)
    return document


def loads_json_bytes(data: bytes) -> Any:
    """Decode strict JSON bytes using RFC 8259 UTF-8 transport semantics."""

    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exception:
        raise StrictJsonError(
            "JSON input is not valid UTF-8 at byte offset "
            f"{exception.start}."
        ) from exception
    return loads_json_document(text)


def load_json_document(source: TextIO | BinaryIO) -> Any:
    """Decode one RFC 8259 document and reject ambiguous representations."""

    content = source.read()
    if isinstance(content, bytes):
        return loads_json_bytes(content)
    return loads_json_document(content)


def load_json_path_or_stdin(
    path_text: str,
    standard_input: TextIO | BinaryIO,
) -> Any:
    """Decode a strict JSON file, or standard input when path is '-'."""

    if path_text == "-":
        binary_input = getattr(standard_input, "buffer", standard_input)
        return load_json_document(binary_input)
    with Path(path_text).open("rb") as source:
        return load_json_document(source)
