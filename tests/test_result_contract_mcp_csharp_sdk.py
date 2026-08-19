#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Regression tests for the official MCP C# SDK interoperability example."""

from __future__ import annotations

import json
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_ROOT = (
    REPOSITORY_ROOT / "examples" / "result_contract" / "mcp-csharp-sdk-v2"
)
PROJECT = EXAMPLE_ROOT / "McpCsharpEvidence.csproj"
GLOBAL_JSON = EXAMPLE_ROOT / "global.json"
PACKAGE_LOCK = EXAMPLE_ROOT / "packages.lock.json"
GENERATOR = EXAMPLE_ROOT / "Program.cs"
README = EXAMPLE_ROOT / "README.md"
EXAMPLES_INDEX = REPOSITORY_ROOT / "examples" / "result_contract" / "README.md"
WORKFLOW = REPOSITORY_ROOT / ".github" / "workflows" / "test.yml"
DEPENDABOT = REPOSITORY_ROOT / ".github" / "dependabot.yml"
MANIFEST = REPOSITORY_ROOT / "MANIFEST.in"


def test_official_mcp_csharp_sdk_example_locks_sdk_and_runtime():
    project = PROJECT.read_text(encoding="utf-8")
    assert "<TargetFramework>net10.0</TargetFramework>" in project
    assert (
        '<PackageReference Include="ModelContextProtocol.Core" '
        'Version="[2.2.0]" />'
    ) in project

    global_json = json.loads(GLOBAL_JSON.read_text(encoding="utf-8"))
    assert global_json["sdk"] == {
        "version": "10.0.400",
        "rollForward": "disable",
        "allowPrerelease": False,
    }

    lock = json.loads(PACKAGE_LOCK.read_text(encoding="utf-8"))
    package = lock["dependencies"]["net10.0"]["ModelContextProtocol.Core"]
    assert package["requested"] == "[2.2.0, 2.2.0]"
    assert package["resolved"] == "2.2.0"
    assert package["contentHash"] == (
        "FeBfXU6T8k+jw4afg4sfxdEX2rL/e5oKOk9ROOGztu9k47+7Bz08sdaToYt2XvMY1"
        "opNbwxYQOFMj6wH9TInhA=="
    )


def test_official_mcp_csharp_sdk_example_uses_real_jsonrpc_transport():
    generator = GENERATOR.read_text(encoding="utf-8")

    for required_fragment in (
        'ProtocolVersion = "2026-07-28"',
        "McpServerTool.Create(",
        "OutputSchema = canonicalSchema",
        "UseStructuredContent = true",
        "new StreamServerTransport(",
        "new StreamClientTransport(",
        "McpServer.Create(",
        "McpClient.CreateAsync(",
        "client.NegotiatedProtocolVersion",
        "client.ListToolsAsync()",
        "listedTool.CallAsync(",
        'jsonrpc_framing_exercised = true',
        'wire_capture_retained = false',
        'independent_adoption = false',
    ):
        assert required_fragment in generator


def test_official_mcp_csharp_sdk_example_states_its_claim_boundary():
    readme = README.read_text(encoding="utf-8")

    assert "not independent adoption" in readme
    assert "does not\nexercise HTTP or SSE" in readme
    assert "does not retain raw frames" in readme
    assert "output_schema_mode: canonical_inline" in readme
    assert "--locked-mode --artifacts-path" in readme
    assert "created and maintained by Alejandro Sánchez" in readme


def test_result_contract_examples_index_exposes_the_csharp_sdk_boundary():
    index = EXAMPLES_INDEX.read_text(encoding="utf-8")

    assert "[C# SDK v2](mcp-csharp-sdk-v2/README.md)" in index
    assert "MCP 2026-07-28" in index
    assert "Paired in-memory streams with newline-delimited JSON-RPC" in index


def test_ci_executes_validates_and_preserves_the_csharp_sdk_evidence():
    workflow = WORKFLOW.read_text(encoding="utf-8")

    for required_fragment in (
        "actions/setup-dotnet@a98b56852c35b8e3190ac28c8c2271da59106c68",
        "mcp-csharp-sdk-v2/global.json",
        "mcp-csharp-sdk-v2/packages.lock.json",
        "dotnet restore --locked-mode --artifacts-path",
        "dotnet build --no-restore --configuration Release --artifacts-path",
        "dotnet format McpCsharpEvidence.csproj --no-restore --verify-no-changes",
        "dotnet run --no-build --configuration Release --artifacts-path",
        "profile: mcp-2026-07-28",
        "success: qzx-mcp-csharp-sdk-v2.2.0-evidence/success.json",
        "qzx-mcp-csharp-sdk-v2.2.0-conformance.json",
        "name: qzx-mcp-csharp-sdk-v2.2.0-evidence",
        "examples/result_contract/mcp-csharp-sdk-v2/Program.cs",
        "retention-days: 14",
    ):
        assert required_fragment in workflow

    dependabot = DEPENDABOT.read_text(encoding="utf-8")
    assert 'package-ecosystem: "nuget"' in dependabot
    assert (
        'directory: "/examples/result_contract/mcp-csharp-sdk-v2"'
        in dependabot
    )
    assert '"ModelContextProtocol.Core"' in dependabot

    manifest = MANIFEST.read_text(encoding="utf-8")
    assert "*.cs *.csproj" in manifest
