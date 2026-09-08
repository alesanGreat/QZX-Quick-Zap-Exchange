#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Validate a QZX Result Contract v1 MCP structured-output profile."""

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
from qzx.core.strict_json import (  # noqa: E402
    StrictJsonError,
    load_json_path_or_stdin,
    loads_json_document,
)


MCP_SPECIFICATION_VERSIONS = (
    "2025-06-18",
    "2025-11-25",
    "2026-07-28",
)
MCP_SPECIFICATION_VERSION = MCP_SPECIFICATION_VERSIONS[-1]
MCP_TOOLS_SPEC_URLS = {
    version: f"https://modelcontextprotocol.io/specification/{version}/server/tools"
    for version in MCP_SPECIFICATION_VERSIONS
}
MCP_TOOLS_SPEC_URL = MCP_TOOLS_SPEC_URLS[MCP_SPECIFICATION_VERSION]
MCP_RESULT_TYPE_VERSION = "2026-07-28"

OUTPUT_SCHEMA_CANONICAL_REF = "canonical_ref"
OUTPUT_SCHEMA_CANONICAL_INLINE = "canonical_inline"
OUTPUT_SCHEMA_CANONICAL_ALLOF = "canonical_allof"
OUTPUT_SCHEMA_STRUCTURAL_CORE = "structural_core"


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
        "--spec-version",
        choices=MCP_SPECIFICATION_VERSIONS,
        default=MCP_SPECIFICATION_VERSION,
        help=(
            "MCP specification revision carried by the evidence. Defaults to "
            f"{MCP_SPECIFICATION_VERSION}."
        ),
    )
    parser.add_argument(
        "--tool-definition",
        help=(
            "Optional JSON file containing the MCP tool definition. When "
            "provided, outputSchema must either embed the canonical QZX schema "
            "or expose a compatible structural QZX core surface."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print one machine-readable validation report.",
    )
    return parser.parse_args()


def _extract_tool_result(document):
    violations = []
    if not isinstance(document, dict):
        return None, ["The MCP input must be a JSON object."]

    has_result = "result" in document
    has_error = "error" in document
    if "jsonrpc" in document or has_result or has_error:
        if document.get("jsonrpc") != "2.0":
            violations.append("A JSON-RPC envelope must declare jsonrpc as '2.0'.")

        if has_result == has_error:
            violations.append(
                "A JSON-RPC response must contain exactly one of result or error."
            )
            return None, violations

        if has_error:
            violations.append(
                "MCP protocol errors are not completed QZX Result Contract results."
            )
            return None, violations

        response_id = document.get("id")
        if not (
            isinstance(response_id, str)
            or (
                isinstance(response_id, int)
                and not isinstance(response_id, bool)
            )
        ):
            violations.append(
                "An MCP JSON-RPC result response must include a string or integer id."
            )

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
            decoded = loads_json_document(item["text"])
        except (json.JSONDecodeError, StrictJsonError):
            continue
        if decoded == structured_content:
            return True
    return False


def _canonical_output_schema_mode(output_schema):
    """Return the strongest reviewable canonical-QZX embedding mode, if any."""
    if not isinstance(output_schema, dict):
        return None

    if output_schema.get("$ref") == RESULT_CONTRACT_SCHEMA_URL:
        return OUTPUT_SCHEMA_CANONICAL_REF

    if output_schema == load_result_contract_schema():
        return OUTPUT_SCHEMA_CANONICAL_INLINE

    all_of = output_schema.get("allOf")
    if isinstance(all_of, list):
        for item in all_of:
            nested_mode = _canonical_output_schema_mode(item)
            if nested_mode in {
                OUTPUT_SCHEMA_CANONICAL_REF,
                OUTPUT_SCHEMA_CANONICAL_INLINE,
                OUTPUT_SCHEMA_CANONICAL_ALLOF,
            }:
                return OUTPUT_SCHEMA_CANONICAL_ALLOF

    return None


def _declares_exact_json_type(schema, expected_type):
    return isinstance(schema, dict) and schema.get("type") == expected_type


def _nonblank_string_schema(schema):
    if not _declares_exact_json_type(schema, "string"):
        return False
    min_length = schema.get("minLength")
    pattern = schema.get("pattern")
    return (
        isinstance(min_length, int)
        and not isinstance(min_length, bool)
        and min_length >= 1
        and pattern == "\\S"
    )


def _error_code_schema(schema):
    if not _declares_exact_json_type(schema, "string"):
        return False
    pattern = schema.get("pattern")
    return pattern == "^[a-z][a-z0-9_]*$"


def _structural_output_schema_violations(output_schema):
    """Check the portable object-schema surface needed for QZX MCP adoption.

    Some maintained MCP SDK 1.x high-level APIs accept only object-shaped output
    schemas. They cannot portably publish an allOf wrapper around an existing
    domain schema. This structural mode therefore checks that the advertised
    output schema makes the stable QZX core fields discoverable and constrained,
    while actual success/failure evidence is still validated against the full
    canonical QZX Result Contract v1 schema.
    """
    violations = []
    if not isinstance(output_schema, dict):
        return ["The MCP tool definition must declare object-valued outputSchema."]

    if output_schema.get("type") != "object":
        violations.append(
            "A structural QZX MCP outputSchema must declare type 'object'."
        )

    required = output_schema.get("required")
    if not isinstance(required, list):
        required = []
    for field in ("success", "message"):
        if field not in required:
            violations.append(
                f"A structural QZX MCP outputSchema must require '{field}'."
            )

    properties = output_schema.get("properties")
    if not isinstance(properties, dict):
        return violations + [
            "A structural QZX MCP outputSchema must declare object properties."
        ]

    if not _declares_exact_json_type(properties.get("success"), "boolean"):
        violations.append(
            "A structural QZX MCP outputSchema must declare success as exactly boolean."
        )

    if not _nonblank_string_schema(properties.get("message")):
        violations.append(
            "A structural QZX MCP outputSchema must constrain message to a "
            "non-empty, non-whitespace string (minLength >= 1 and a \\S pattern)."
        )

    declares_failure_evidence = _nonblank_string_schema(
        properties.get("error")
    ) or _error_code_schema(properties.get("error_code"))
    if not declares_failure_evidence:
        violations.append(
            "A structural QZX MCP outputSchema must declare at least one QZX "
            "failure-evidence field: nonblank string 'error' or canonical "
            "string 'error_code'."
        )

    return violations


def _assess_output_schema(tool_definition):
    """Return violations, warnings, and a stable output-schema evidence mode."""
    if not isinstance(tool_definition, dict):
        return ["The MCP tool definition must be a JSON object."], [], None

    output_schema = tool_definition.get("outputSchema")
    if not isinstance(output_schema, dict):
        return [
            "The MCP tool definition must declare object-valued outputSchema."
        ], [], None

    canonical_mode = _canonical_output_schema_mode(output_schema)
    if canonical_mode is not None:
        return [], [], canonical_mode

    structural_violations = _structural_output_schema_violations(output_schema)
    if structural_violations:
        return structural_violations, [], None

    return (
        [],
        [
            "outputSchema exposes the QZX core structurally but does not embed "
            "the canonical QZX schema. The submitted runtime evidence is "
            "validated against the full Result Contract, but outputSchema alone "
            "does not guarantee every QZX invariant."
        ],
        OUTPUT_SCHEMA_STRUCTURAL_CORE,
    )


def validate_mcp_profile(
    document,
    tool_definition=None,
    specification_version=MCP_SPECIFICATION_VERSION,
):
    """Return deterministic QZX MCP profile violations, warnings, and facts."""
    if specification_version not in MCP_TOOLS_SPEC_URLS:
        raise ValueError(f"Unsupported MCP specification revision: {specification_version}")

    result, violations = _extract_tool_result(document)
    warnings = []

    schema_violations = []
    schema_warnings = []
    output_schema_mode = None
    if tool_definition is not None:
        schema_violations, schema_warnings, output_schema_mode = _assess_output_schema(
            tool_definition
        )

    details = {
        "mcp_specification": specification_version,
        "mcp_tools_spec": MCP_TOOLS_SPEC_URLS[specification_version],
        "contract": RESULT_CONTRACT_SCHEMA_URL,
        "output_schema_checked": tool_definition is not None,
        "output_schema_mode": output_schema_mode,
        "backcompat_text_matches": False,
    }

    if result is None:
        violations.extend(schema_violations)
        warnings.extend(schema_warnings)
        return violations, warnings, details

    result_type = result.get("resultType")
    if specification_version == MCP_RESULT_TYPE_VERSION:
        if result_type != "complete":
            violations.append(
                "The MCP 2026-07-28 profile applies only to resultType 'complete'."
            )
    elif result_type is not None and result_type != "complete":
        violations.append(
            f"The MCP {specification_version} profile applies only to completed "
            "tool results."
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

    is_error_explicit = "isError" in result
    is_error_value = result.get("isError")
    is_error_valid = not is_error_explicit or isinstance(is_error_value, bool)
    if not is_error_valid:
        violations.append("MCP isError must be a boolean when present.")
    effective_is_error = is_error_value if isinstance(is_error_value, bool) else False
    details["mcp_is_error_explicit"] = is_error_explicit
    details["mcp_is_error_effective"] = effective_is_error

    if isinstance(structured_content, dict):
        success = structured_content.get("success")
        if isinstance(success, bool) and is_error_valid:
            if effective_is_error != (not success):
                violations.append(
                    "Effective MCP isError must equal !structuredContent.success "
                    "for a completed QZX MCP profile result. MCP treats omitted "
                    "isError as false."
                )

        backcompat_matches = _backcompat_text_matches(content, structured_content)
        details["backcompat_text_matches"] = backcompat_matches
        if not backcompat_matches:
            warnings.append(
                "No TextContent block serializes the complete structuredContent "
                "object. MCP recommends this for backwards compatibility."
            )

    violations.extend(schema_violations)
    warnings.extend(schema_warnings)

    return violations, warnings, details


def main() -> int:
    args = parse_args()
    specification_version = args.spec_version
    tools_spec_url = MCP_TOOLS_SPEC_URLS[specification_version]
    try:
        document = load_json_path_or_stdin(args.path, sys.stdin)
        tool_definition = (
            load_json_path_or_stdin(args.tool_definition, sys.stdin)
            if args.tool_definition
            else None
        )
        violations, warnings, profile_details = validate_mcp_profile(
            document,
            tool_definition,
            specification_version,
        )
        result = {
            "success": not violations,
            "message": (
                "The MCP result conforms to the QZX Result Contract v1 "
                f"MCP {specification_version} interoperability profile."
                if not violations
                else "The MCP result violates the QZX Result Contract v1 "
                f"MCP {specification_version} interoperability profile."
            ),
            "warnings": warnings,
            "details": {
                **profile_details,
                "violations": violations,
            },
        }
    except (OSError, json.JSONDecodeError, StrictJsonError) as exception:
        result = {
            "success": False,
            "message": "The MCP profile input could not be read as JSON.",
            "error": str(exception),
            "error_code": "invalid_json_input",
            "details": {
                "mcp_specification": specification_version,
                "mcp_tools_spec": tools_spec_url,
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
