#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Regression tests for the official MCP Go SDK interoperability example."""

from __future__ import annotations

from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_ROOT = (
    REPOSITORY_ROOT / "examples" / "result_contract" / "mcp-go-sdk-v1"
)
GO_MOD = EXAMPLE_ROOT / "go.mod"
GO_SUM = EXAMPLE_ROOT / "go.sum"
GENERATOR = EXAMPLE_ROOT / "main.go"
README = EXAMPLE_ROOT / "README.md"
WORKFLOW = REPOSITORY_ROOT / ".github" / "workflows" / "test.yml"
DEPENDABOT = REPOSITORY_ROOT / ".github" / "dependabot.yml"


def test_official_mcp_go_sdk_example_locks_the_stable_sdk():
    go_mod = GO_MOD.read_text(encoding="utf-8")
    assert "go 1.25.0" in go_mod
    assert "github.com/modelcontextprotocol/go-sdk v1.6.1" in go_mod

    go_sum = GO_SUM.read_text(encoding="utf-8")
    assert (
        "github.com/modelcontextprotocol/go-sdk v1.6.1 "
        "h1:0zOSupjKUxPKSocPT1Wtago+mUHU2/uZ4xSOY0FGReU=" in go_sum
    )


def test_official_mcp_go_sdk_example_uses_real_jsonrpc_transport():
    generator = GENERATOR.read_text(encoding="utf-8")

    for required_fragment in (
        'protocolVersion = "2025-11-25"',
        "mcp.NewServer(",
        "mcp.AddTool(server",
        "OutputSchema: json.RawMessage(schemaBytes)",
        "mcp.NewInMemoryTransports()",
        "server.Connect(ctx, serverTransport, nil)",
        "client.Connect(ctx, clientTransport, nil)",
        "clientSession.InitializeResult().ProtocolVersion",
        "clientSession.ListTools(ctx, nil)",
        "clientSession.CallTool(ctx",
        '"jsonrpc_framing_exercised": true',
        '"wire_capture_retained":     false',
        '"independent_adoption":      false',
    ):
        assert required_fragment in generator


def test_official_mcp_go_sdk_example_states_its_claim_boundary():
    readme = README.read_text(encoding="utf-8")

    assert "not independent adoption" in readme
    assert "does not exercise\nHTTP or SSE" in readme
    assert "does not retain raw frames" in readme
    assert "output_schema_mode: canonical_inline" in readme
    assert "created and maintained by Alejandro Sánchez" in readme


def test_ci_executes_validates_and_preserves_the_go_sdk_evidence():
    workflow = WORKFLOW.read_text(encoding="utf-8")

    for required_fragment in (
        "actions/setup-go@b7ad1dad31e06c5925ef5d2fc7ad053ef454303e",
        'go-version: "1.25.1"',
        "mcp-go-sdk-v1/go.sum",
        "go run -mod=readonly",
        "go mod verify",
        "profile: mcp-2025-11-25",
        "success: qzx-mcp-go-sdk-v1.6.1-evidence/success.json",
        "qzx-mcp-go-sdk-v1.6.1-conformance.json",
        "name: qzx-mcp-go-sdk-v1.6.1-evidence",
        "examples/result_contract/mcp-go-sdk-v1/main.go",
        "retention-days: 14",
    ):
        assert required_fragment in workflow

    dependabot = DEPENDABOT.read_text(encoding="utf-8")
    assert 'package-ecosystem: "gomod"' in dependabot
    assert 'directory: "/examples/result_contract/mcp-go-sdk-v1"' in dependabot
    assert '"github.com/modelcontextprotocol/go-sdk"' in dependabot
