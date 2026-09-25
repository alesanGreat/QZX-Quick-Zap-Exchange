"""Explicit starter result contracts for generated documentation and agents."""

from copy import deepcopy

_COMMON_PROPERTIES = {
    "success": {"type": "boolean"},
    "message": {"type": "string"},
    "project_name": {
        "description": "Normalized project name on success; original input on validation errors."
    },
    "project_path": {"type": "string"},
    "with_tests": {"type": "boolean"},
    "files_created": {"type": "array", "items": {"type": "string"}},
    "timestamp": {"type": "string"},
    "partial": {"type": "boolean"},
    "error": {"type": "string"},
    "error_code": {"type": "string"},
}
_STEP = {
    "type": "object",
    "required": ["id", "description", "cwd", "argv"],
    "properties": {
        "id": {"type": "string", "enum": ["run", "install", "test", "build"]},
        "description": {"type": "string"},
        "cwd": {"type": "string"},
        "argv": {"type": "array", "minItems": 1, "items": {"type": "string"}},
    },
    "additionalProperties": True,
}
_ENVIRONMENT = {
    "type": "object",
    "required": ["requested", "status"],
    "properties": {
        "requested": {"type": "boolean"},
        "status": {"enum": ["not_requested", "created", "failed"]},
        "path": {"type": "string"},
        "python": {"type": "string"},
        "message": {"type": "string"},
    },
    "additionalProperties": True,
    "allOf": [{
        "if": {"properties": {"status": {"const": "created"}}},
        "then": {"required": ["path", "python"],
                 "properties": {"requested": {"const": True}}},
    }],
}


def starter_result_schema(*, python: bool = False) -> dict:
    """Return an independent schema without requiring success fields on errors."""
    properties = deepcopy(_COMMON_PROPERTIES)
    if python:
        properties.update({
            "create_venv": {"type": "boolean"},
            "requested_project_name": {"type": "string"},
            "name_was_normalized": {"type": "boolean"},
            "virtual_environment": deepcopy(_ENVIRONMENT),
            "warnings": {"type": "array", "items": {"type": "string"}},
            "report": {"type": "string"},
            "next_steps": {
                "type": "array", "items": deepcopy(_STEP),
                "description": "Suggested argv/cwd actions; QZX has not executed them.",
            },
        })
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": ["success", "message"],
        "properties": properties,
        "additionalProperties": True,
    }
