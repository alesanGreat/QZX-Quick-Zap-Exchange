#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Validate the QZX Result Contract v1 MCP 2026-07-28 interoperability profile."""

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
    RESULT_CONTRACT_SCHEMA_URL,
    load_result_contract_schema,
    result_contract_violations,
)


MCP_SPECIFICATION_VERSION = "2026-07-28"
MCP_TOOLS_SPEC_URL = (
    "https://modelcontextprotocol.io/specification/2026-07-28/server/tools"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "path",
        nargs="?",
        default="-",
        help=(
            "MCP CallToolResult JSON file or full JSON-RPC response, or '-' "
            "to read stdin."
        ),
    )
    parser.add_argument(
        "--tool-definition",
        help=(
            "Optional JSON file containing the MCP tool definition. When "
            "provided, outputSchema must use the canonical QZX schema by "
            "direct $ref or exact inline schema."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print one machine-readable validation report.",
    )
    return parser.parse_args()


def load_document(path: str):
    if path == "-":
        return json.load(sys.stdin)
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _extract_tool_result(document):
    violations = []
    if not isinstance(document, dict):
        return None, ["The MCP input must be a JSON object."]

    if "error" in document and "result" not in document:
        return None, [
            "MCP protocol errors are not completed QZX Result Contract results."
        ]

    if "jsonrpc" in document or "result" in document:
        if document.get("jsonrpc") != "2.0":
            violations.append("A JSON-RPC envelope must declare jsonrpc as '2.0'.")
        result = document.get("result")
        if not isinstance(result, dict):
            violations.append(
                "A JSON-RPC MCP response must contain an object-valued result."
            )
            return None, violations
        return result, violations

    return document, violations


def _backcompat_text_matches(content, structured_content):
    if not isinstance(content, list):
        return False
    for item in content:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "text" or not isinstance(item.get("text"), str):
            continue
        try:
            decoded = json.loads(item["text"])
        except json.JSONDecodeError:
            continue
        if decoded == structured_content:
            return True
    return False


def _output_schema_violations(tool_definition):
    if not isinstance(tool_definition, dict):
        return ["The MCP tool definition must be a JSON object."]

    output_schema = tool_definition.get("outputSchema")
    if not isinstance(output_schema, dict):
        return [
            "The MCP tool definition must declare object-valued outputSchema."
        ]

    if output_schema.get("$ref") == RESULT_CONTRACT_SCHEMA_URL:
        return []

    if output_schema == load_result_contract_schema():
        return []

    return [
        "outputSchema must directly reference the canonical QZX Result "
        "Contract v1 schema or inline that schema exactly."
    ]


def validate_mcp_profile(document, tool_definition=None):
    """Return deterministic QZX MCP profile violations, warnings, and facts."""
    result, violations = _extract_tool_result(document)
    warnings = []

    details = {
        "mcp_specification": MCP_SPECIFICATION_VERSION,
        "mcp_tools_spec": MCP_TOOLS_SPEC_URL,
        "contract": RESULT_CONTRACT_SCHEMA_URL,
        "output_schema_checked": tool_definition is not None,
        "backcompat_text_matches": False,
    }

    if result is None:
        if tool_definition is not None:
            violations.extend(_output_schema_violations(tool_definition))
        return violations, warnings, details

    if result.get("resultType") != "complete":
        violations.append(
            "The MCP 2026-07-28 profile applies only to resultType 'complete'."
        )

    content = result.get("content")
    if not isinstance(content, list):
        violations.append("A completed MCP tool result must contain a content array.")

    if "structuredContent" not in result:
        structured_content = None
        violations.append(
            "A QZX MCP profile result must contain structuredContent."
        )
    else:
        structured_content = result["structuredContent"]
        core_violations = result_contract_violations(structured_content)
        violations.extend(
            f"structuredContent: {violation}" for violation in core_violations
        )

    is_error = result.get("isError")
    if not isinstance(is_error, bool):
        violations.append(
            "A QZX MCP profile result must declare isError as an explicit boolean."
        )

    if isinstance(structured_content, dict):
        success = structured_content.get("success")
        if isinstance(success, bool) and isinstance(is_error, bool):
            if is_error != (not success):
                violations.append(
                    "isError must equal !structuredContent.success for a "
                    "completed QZX MCP profile result."
                )

        backcompat_matches = _backcompat_text_matches(content, structured_content)
        details["backcompat_text_matches"] = backcompat_matches
        if not backcompat_matches:
            warnings.append(
                "No TextContent block serializes the complete structuredContent "
                "object. MCP recommends this for backwards compatibility."
            )

    if tool_definition is not None:
        violations.extend(_output_schema_violations(tool_definition))

    return violations, warnings, details


def main() -> int:
    args = parse_args()
    try:
        document = load_document(args.path)
        tool_definition = (
            load_document(args.tool_definition)
            if args.tool_definition
            else None
        )
        violations, warnings, profile_details = validate_mcp_profile(
            document,
            tool_definition,
        )
        result = {
            "success": not violations,
            "message": (
                "The MCP result conforms to the QZX Result Contract v1 "
                "MCP 2026-07-28 interoperability profile."
                if not violations
                else "The MCP result violates the QZX Result Contract v1 "
                "MCP 2026-07-28 interoperability profile."
            ),
            "warnings": warnings,
            "details": {
                **profile_details,
                "violations": violations,
            },
        }
    except (OSError, json.JSONDecodeError) as exception:
        result = {
            "success": False,
            "message": "The MCP profile input could not be read as JSON.",
            "error": str(exception),
            "error_code": "invalid_json_input",
            "details": {
                "mcp_specification": MCP_SPECIFICATION_VERSION,
                "mcp_tools_spec": MCP_TOOLS_SPEC_URL,
                "contract": RESULT_CONTRACT_SCHEMA_URL,
                "violations": [],
            },
        }

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        prefix = "[OK]" if result["success"] else "[FAIL]"
        print(f"{prefix} {result['message']}")
        for violation in result["details"].get("violations", []):
            print(f"  - {violation}")
        for warning in result.get("warnings", []):
            print(f"  [WARN] {warning}")
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
