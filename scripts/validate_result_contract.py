#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Validate one JSON document against the QZX Result Contract v1 core."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from qzx.core.result_contract import (  # noqa: E402
    JsonInteroperabilityError,
    RESULT_CONTRACT_SCHEMA_URL,
    load_interoperable_json,
    result_contract_violations,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "path",
        nargs="?",
        default="-",
        help="JSON file to validate, or '-' to read stdin.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print one machine-readable validation report.",
    )
    return parser.parse_args()


def load_document(path: str):
    if path == "-":
        return load_interoperable_json(sys.stdin, source="standard input")
    with Path(path).open("r", encoding="utf-8") as handle:
        return load_interoperable_json(handle, source=path)


def main() -> int:
    args = parse_args()
    try:
        document = load_document(args.path)
        violations = result_contract_violations(document)
        result = {
            "success": not violations,
            "message": (
                "The JSON document conforms to QZX Result Contract v1."
                if not violations
                else "The JSON document violates QZX Result Contract v1."
            ),
            "details": {
                "contract": RESULT_CONTRACT_SCHEMA_URL,
                "violations": violations,
            },
        }
    except (OSError, json.JSONDecodeError, JsonInteroperabilityError) as exception:
        result = {
            "success": False,
            "message": "The input could not be read as one JSON document.",
            "error": str(exception),
            "error_code": "invalid_json_input",
            "details": {
                "contract": RESULT_CONTRACT_SCHEMA_URL,
                "violations": [],
            },
        }

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        prefix = "[OK]" if result["success"] else "[FAIL]"
        print(f"{prefix} {result['message']}")
        if result.get("error"):
            print(f"  - {result['error']}")
        for violation in result["details"]["violations"]:
            print(f"  - {violation}")
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
