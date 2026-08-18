#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Regression tests for the official MCP Python SDK v2 evidence example."""

from __future__ import annotations

from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_ROOT = REPOSITORY_ROOT / "examples" / "result_contract" / "mcp-python-sdk-v2"
REQUIREMENTS_INPUT = EXAMPLE_ROOT / "requirements.in"
REQUIREMENTS_LOCK = EXAMPLE_ROOT / "requirements.txt"
GENERATOR = EXAMPLE_ROOT / "generate_evidence.py"
README = EXAMPLE_ROOT / "README.md"
WORKFLOW = REPOSITORY_ROOT / ".github" / "workflows" / "test.yml"


def test_official_mcp_python_sdk_example_locks_the_stable_sdk():
    requirements = REQUIREMENTS_INPUT.read_text(encoding="utf-8")
    assert "mcp==2.0.0" in requirements
    assert 'pywin32==312 ; sys_platform == "win32"' in requirements

    lockfile = REQUIREMENTS_LOCK.read_text(encoding="utf-8")
    assert "--generate-hashes" in lockfile
    assert "mcp==2.0.0" in lockfile
    assert "mcp-types==2.0.0" in lockfile
    assert 'pywin32==312 ; sys_platform == "win32"' in lockfile


def test_official_mcp_python_sdk_example_uses_the_modern_protocol_path():
    generator = GENERATOR.read_text(encoding="utf-8")

    for required_fragment in (
        "from mcp.client import Client",
        "from mcp.server import Server",
        'PROTOCOL_VERSION = "2026-07-28"',
        "output_schema=contract_schema",
        "Client(server, mode=PROTOCOL_VERSION)",
        "await client.list_tools()",
        'await client.call_tool(TOOL_NAME, {"fail": False})',
        'model_dump(by_alias=True, exclude_none=True, mode="json")',
        '"transport": "in_process_direct_dispatcher"',
        '"jsonrpc_framing_exercised": False',
        '"independent_adoption": False',
    ):
        assert required_fragment in generator


def test_official_mcp_python_sdk_example_states_its_claim_boundary():
    readme = README.read_text(encoding="utf-8")

    assert "not independent adoption" in readme
    assert "does not exercise HTTP, SSE, or\nJSON-RPC framing" in readme
    assert "output_schema_mode: canonical_inline" in readme
    assert "created and maintained by Alejandro Sánchez" in readme


def test_ci_executes_validates_and_preserves_the_python_sdk_evidence():
    workflow = WORKFLOW.read_text(encoding="utf-8")

    for required_fragment in (
        "mcp-python-sdk-v2/requirements.txt",
        "-m pip install",
        "--disable-pip-version-check",
        "--require-hashes",
        "mcp-python-sdk-v2/generate_evidence.py",
        "qzx-mcp-python-sdk-v2-conformance.json",
        "success: qzx-mcp-python-sdk-v2-evidence/success.json",
        "name: qzx-mcp-python-sdk-v2-evidence",
        "examples/result_contract/mcp-python-sdk-v2/README.md",
        "retention-days: 14",
    ):
        assert required_fragment in workflow
