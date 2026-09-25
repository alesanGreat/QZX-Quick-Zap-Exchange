#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Schema-level regression tests for QZX conformance receipt v1."""

from __future__ import annotations

import copy
import importlib.util
import json
import re
from pathlib import Path
from typing import Any

from qzx.core.result_contract import result_contract_violations


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = (
    REPOSITORY_ROOT
    / "src"
    / "qzx"
    / "resources"
    / "schemas"
    / "result-contract-conformance-receipt-v1.schema.json"
)
VALIDATOR_PATH = REPOSITORY_ROOT / "scripts" / "validate_result_contract_evidence.py"
FIXTURE_ROOT = REPOSITORY_ROOT / "examples" / "result_contract"

spec = importlib.util.spec_from_file_location("qzx_evidence_validator_for_schema", VALIDATOR_PATH)
validator = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(validator)


def _resolve_ref(root: dict[str, Any], reference: str) -> dict[str, Any]:
    if not reference.startswith("#/"):
        raise AssertionError(f"Test validator only supports local references: {reference}")
    value: Any = root
    for raw_part in reference[2:].split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        value = value[part]
    assert isinstance(value, dict)
    return value


def _type_matches(expected: str, instance: Any) -> bool:
    checks = {
        "object": lambda value: isinstance(value, dict),
        "array": lambda value: isinstance(value, list),
        "string": lambda value: isinstance(value, str),
        "boolean": lambda value: isinstance(value, bool),
        "integer": lambda value: isinstance(value, int) and not isinstance(value, bool),
        "number": lambda value: (
            isinstance(value, (int, float)) and not isinstance(value, bool)
        ),
        "null": lambda value: value is None,
    }
    return checks[expected](instance)


def _matches(schema: dict[str, Any], instance: Any, root: dict[str, Any]) -> bool:
    referenced = _reference_match(schema, instance, root)
    if referenced is not None:
        return referenced
    if not _combinators_match(schema, instance, root):
        return False
    if not _scalar_constraints_match(schema, instance):
        return False
    if isinstance(instance, dict):
        return _object_constraints_match(schema, instance, root)
    if isinstance(instance, list):
        return _array_constraints_match(schema, instance, root)
    return True


def _reference_match(schema, instance, root):
    if "$ref" not in schema:
        return None
    return _matches(_resolve_ref(root, schema["$ref"]), instance, root)


def _combinators_match(schema, instance, root):
    if "allOf" in schema and not all(
        _matches(item, instance, root) for item in schema["allOf"]
    ):
        return False
    if "anyOf" in schema and not any(
        _matches(item, instance, root) for item in schema["anyOf"]
    ):
        return False
    return _conditional_match(schema, instance, root)


def _conditional_match(schema, instance, root):
    if "if" not in schema:
        return True
    condition = _matches(schema["if"], instance, root)
    if condition and "then" in schema:
        return _matches(schema["then"], instance, root)
    if not condition and "else" in schema:
        return _matches(schema["else"], instance, root)
    return True


def _scalar_constraints_match(schema, instance):
    if "const" in schema and instance != schema["const"]:
        return False
    if "enum" in schema and instance not in schema["enum"]:
        return False
    expected_type = schema.get("type")
    if isinstance(expected_type, str):
        if not _type_matches(expected_type, instance):
            return False
    elif isinstance(expected_type, list):
        if not any(
            _type_matches(item, instance) for item in expected_type
        ):
            return False
    if isinstance(instance, str):
        return _string_constraints_match(schema, instance)
    return True


def _string_constraints_match(schema, instance):
    if len(instance) < schema.get("minLength", 0):
        return False
    pattern = schema.get("pattern")
    return not (
        isinstance(pattern, str)
        and re.search(pattern, instance) is None
    )


def _object_constraints_match(schema, instance, root):
    required = schema.get("required", [])
    if any(name not in instance for name in required):
        return False
    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        return True
    for name, subschema in properties.items():
        if name in instance and not _matches(
            subschema,
            instance[name],
            root,
        ):
            return False
    if schema.get("additionalProperties") is False:
        return not bool(set(instance) - set(properties))
    return True


def _array_constraints_match(schema, instance, root):
    if len(instance) < schema.get("minItems", 0):
        return False
    max_items = schema.get("maxItems")
    if isinstance(max_items, int) and len(instance) > max_items:
        return False
    prefix_items = schema.get("prefixItems", [])
    if not _prefix_items_match(prefix_items, instance, root):
        return False
    return _remaining_items_match(
        schema.get("items"),
        prefix_items,
        instance,
        root,
    )


def _prefix_items_match(prefix_items, instance, root):
    if not isinstance(prefix_items, list):
        return True
    return all(
        index >= len(instance)
        or _matches(subschema, instance[index], root)
        for index, subschema in enumerate(prefix_items)
    )


def _remaining_items_match(items, prefix_items, instance, root):
    prefix_count = len(prefix_items) if isinstance(prefix_items, list) else 0
    if items is False and len(instance) > prefix_count:
        return False
    if not isinstance(items, dict):
        return True
    return all(
        _matches(items, item, root)
        for item in instance[prefix_count:]
    )


def _receipt(*, profile: str, with_tool_definition: bool = False) -> dict[str, Any]:
    is_mcp = profile in validator.MCP_PROFILES
    arguments = {
        "profile": profile,
        "success_path": str(
            FIXTURE_ROOT / ("mcp-success.json" if is_mcp else "valid-success.json")
        ),
        "failure_path": str(
            FIXTURE_ROOT / ("mcp-failure.json" if is_mcp else "valid-failure.json")
        ),
    }
    if with_tool_definition:
        arguments["tool_definition_path"] = str(
            FIXTURE_ROOT / "mcp-tool-definition.json"
        )
    return validator.validate_evidence(**arguments)


def test_receipt_schema_accepts_pass_and_fail_receipts():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    receipts = [
        _receipt(profile=validator.PROFILE_CORE),
        *[
            _receipt(profile=profile, with_tool_definition=True)
            for profile in validator.MCP_PROFILES
        ],
        _receipt(profile=validator.PROFILE_MCP, with_tool_definition=False),
    ]

    assert schema["$id"] == validator.CONFORMANCE_RECEIPT_SCHEMA_URL
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert receipts[0]["success"] is True
    assert all(receipt["success"] is True for receipt in receipts[1:-1])
    assert receipts[-1]["success"] is False
    for receipt in receipts:
        assert receipt["receipt_schema"] == schema["$id"]
        assert _matches(schema, receipt, schema)
        assert result_contract_violations(receipt) == []
    assert "error_code" not in receipts[0]
    assert all("error_code" not in receipt for receipt in receipts[1:-1])
    assert receipts[-1]["error_code"] == "conformance_failed"
    for receipt in receipts[1:]:
        success_facts = receipt["details"]["cases"][0]["profile_facts"]
        failure_facts = receipt["details"]["cases"][1]["profile_facts"]
        assert success_facts["mcp_is_error_explicit"] is True
        assert success_facts["mcp_is_error_effective"] is False
        assert failure_facts["mcp_is_error_explicit"] is True
        assert failure_facts["mcp_is_error_effective"] is True


def test_receipt_schema_remains_compatible_with_older_mcp_receipts():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    receipt = _receipt(profile=validator.MCP_PROFILES[0], with_tool_definition=True)

    receipt["details"].pop("validation_materials")
    for case in receipt["details"]["cases"]:
        case["profile_facts"].pop("mcp_is_error_explicit")
        case["profile_facts"].pop("mcp_is_error_effective")

    assert _matches(schema, receipt, schema)


def test_receipt_schema_accepts_the_previous_validation_material_set():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    receipt = _receipt(profile=validator.PROFILE_CORE)

    receipt["details"]["validation_materials"].pop("json_decoder")

    assert _matches(schema, receipt, schema)


def test_receipt_schema_rejects_unknown_fields_and_role_swaps():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    receipt = _receipt(profile=validator.PROFILE_CORE)

    unknown = copy.deepcopy(receipt)
    unknown["unexpected"] = True
    assert not _matches(schema, unknown, schema)

    swapped = copy.deepcopy(receipt)
    swapped["details"]["cases"][0]["expected_success"] = False
    assert not _matches(schema, swapped, schema)

    wrong_material_path = copy.deepcopy(receipt)
    wrong_material_path["details"]["validation_materials"]["contract_schema"][
        "repository_path"
    ] = "somewhere-else.json"
    assert not _matches(schema, wrong_material_path, schema)

    wrong_material_digest = copy.deepcopy(receipt)
    wrong_material_digest["details"]["validation_materials"]["contract_schema"][
        "sha256"
    ] = "not-a-sha256"
    assert not _matches(schema, wrong_material_digest, schema)

    failed_without_error_code = _receipt(profile=validator.PROFILE_MCP)
    failed_without_error_code.pop("error_code")
    assert failed_without_error_code["success"] is False
    assert not _matches(schema, failed_without_error_code, schema)


def test_receipt_schema_is_strict_but_profile_facts_allow_core_empty_object():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    receipt = _receipt(profile=validator.PROFILE_CORE)

    assert receipt["details"]["cases"][0]["profile_facts"] == {}
    assert _matches(schema, receipt, schema)
    assert schema["additionalProperties"] is False
    assert schema["properties"]["details"]["additionalProperties"] is False
    assert schema["$defs"]["case"]["additionalProperties"] is False
