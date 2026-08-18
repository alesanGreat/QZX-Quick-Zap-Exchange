#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Generate QZX Result Contract evidence with the official MCP Python SDK v2."""

from __future__ import annotations

import asyncio
from importlib.metadata import version
import json
from pathlib import Path
import platform
import sys
from typing import Any

from mcp.client import Client
from mcp.server import Server
import mcp.types as types


PROTOCOL_VERSION = "2026-07-28"
TOOL_NAME = "lookup_widget"
EXAMPLE_DIRECTORY = Path(__file__).resolve().parent
REPOSITORY_ROOT = EXAMPLE_DIRECTORY.parents[2]
SCHEMA_PATH = (
    REPOSITORY_ROOT
    / "src"
    / "qzx"
    / "resources"
    / "schemas"
    / "result-contract-v1.schema.json"
)


def parse_output_directory(arguments: list[str]) -> Path:
    """Accept one output directory and tolerate a package-runner separator."""

    positional = [argument for argument in arguments if argument != "--"]
    if len(positional) != 1:
        raise ValueError("Usage: python generate_evidence.py <output-directory>")
    return Path(positional[0]).expanduser().resolve()


def success_document() -> dict[str, Any]:
    return {
        "success": True,
        "message": "The requested widget was returned.",
        "details": {"widget_id": "widget-1", "status": "ready"},
    }


def failure_document() -> dict[str, Any]:
    return {
        "success": False,
        "message": "The requested widget was not found.",
        "error_code": "widget_not_found",
        "details": {"widget_id": "missing-widget"},
    }


def build_server(contract_schema: dict[str, Any]) -> Server[Any]:
    tool = types.Tool(
        name=TOOL_NAME,
        description="Look up one synthetic widget for a QZX interoperability test.",
        input_schema={
            "type": "object",
            "properties": {"fail": {"type": "boolean"}},
            "required": ["fail"],
            "additionalProperties": False,
        },
        output_schema=contract_schema,
    )

    async def list_tools(
        _context: Any,
        _params: types.PaginatedRequestParams | None,
    ) -> types.ListToolsResult:
        return types.ListToolsResult(tools=[tool])

    async def call_tool(
        _context: Any,
        params: types.CallToolRequestParams,
    ) -> types.CallToolResult:
        if params.name != TOOL_NAME:
            raise ValueError(f"Unknown synthetic tool: {params.name}")
        fail = bool((params.arguments or {}).get("fail"))
        document = failure_document() if fail else success_document()
        return types.CallToolResult(
            content=[
                types.TextContent(
                    text=json.dumps(
                        document,
                        ensure_ascii=False,
                        separators=(",", ":"),
                        sort_keys=True,
                    )
                )
            ],
            structured_content=document,
            is_error=fail,
        )

    return Server(
        "qzx-result-contract-python-sdk-evidence",
        version="1.0.0",
        on_list_tools=list_tools,
        on_call_tool=call_tool,
    )


def wire_document(model: Any) -> dict[str, Any]:
    """Serialize an SDK model with its MCP wire aliases."""

    return model.model_dump(by_alias=True, exclude_none=True, mode="json")


async def generate(output_directory: Path) -> dict[str, Any]:
    contract_schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    server = build_server(contract_schema)

    async with Client(server, mode=PROTOCOL_VERSION) as client:
        if client.protocol_version != PROTOCOL_VERSION:
            raise RuntimeError(
                f"Expected MCP {PROTOCOL_VERSION}, got {client.protocol_version}."
            )

        listed_tools = await client.list_tools()
        matching_tools = [tool for tool in listed_tools.tools if tool.name == TOOL_NAME]
        if len(matching_tools) != 1:
            raise RuntimeError(
                "The official MCP client did not discover lookup_widget."
            )

        success_result = await client.call_tool(TOOL_NAME, {"fail": False})
        failure_result = await client.call_tool(TOOL_NAME, {"fail": True})

    tool_definition = wire_document(matching_tools[0])
    success = wire_document(success_result)
    failure = wire_document(failure_result)

    if tool_definition.get("outputSchema") != contract_schema:
        raise RuntimeError(
            "The official SDK changed the canonical inline output schema."
        )
    if (
        success.get("resultType") != "complete"
        or failure.get("resultType") != "complete"
    ):
        raise RuntimeError("The official SDK did not retain MCP completed-result tags.")
    if success.get("isError") is not False or failure.get("isError") is not True:
        raise RuntimeError("The official SDK observed an inconsistent result pair.")

    evidence_metadata = {
        "evidence_kind": "qzx_maintained_reference",
        "independent_adoption": False,
        "protocol": PROTOCOL_VERSION,
        "protocol_era": "modern",
        "transport": "in_process_direct_dispatcher",
        "jsonrpc_framing_exercised": False,
        "serialization": "pydantic_model_dump_by_alias",
        "packages": {
            "mcp": version("mcp"),
            "mcp-types": version("mcp-types"),
            "pydantic": version("pydantic"),
        },
        "runtime": {
            "implementation": platform.python_implementation(),
            "python": platform.python_version(),
            "platform": sys.platform,
            "architecture": platform.machine(),
        },
        "output_directory": str(output_directory),
        "files": [
            "tool-definition.json",
            "success.json",
            "failure.json",
            "evidence-metadata.json",
        ],
    }

    output_directory.mkdir(parents=True, exist_ok=True)
    documents = (
        ("tool-definition.json", tool_definition),
        ("success.json", success),
        ("failure.json", failure),
        ("evidence-metadata.json", evidence_metadata),
    )
    for filename, document in documents:
        (output_directory / filename).write_text(
            json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    return evidence_metadata


def main() -> int:
    output_directory = parse_output_directory(sys.argv[1:])
    metadata = asyncio.run(generate(output_directory))
    print(
        json.dumps(
            {
                "success": True,
                "message": "Official MCP Python SDK v2 reference evidence generated.",
                "details": metadata,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
