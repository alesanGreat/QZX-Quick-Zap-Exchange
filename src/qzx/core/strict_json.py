#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Strict RFC 8259 JSON decoding for interoperable evidence."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, TextIO


class StrictJsonError(ValueError):
    """Raised when valid-looking input is not interoperable RFC 8259 JSON."""


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


def loads_json_document(text: str) -> Any:
    """Decode one RFC 8259 document from text with strict evidence rules."""

    return json.loads(
        text,
        object_pairs_hook=_object_with_unique_names,
        parse_constant=_reject_non_json_constant,
        parse_float=_finite_float,
    )


def load_json_document(source: TextIO) -> Any:
    """Decode one RFC 8259 document and reject ambiguous object members."""

    return loads_json_document(source.read())


def load_json_path_or_stdin(path_text: str, standard_input: TextIO) -> Any:
    """Decode a strict JSON file, or standard input when the path is ``-``."""

    if path_text == "-":
        return load_json_document(standard_input)
    with Path(path_text).open("r", encoding="utf-8") as source:
        return load_json_document(source)
