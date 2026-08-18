#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Regression tests for the official MCP TypeScript SDK v2 evidence example."""

from __future__ import annotations

import json
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_ROOT = (
    REPOSITORY_ROOT / "examples" / "result_contract" / "mcp-typescript-sdk-v2"
)
PACKAGE = EXAMPLE_ROOT / "package.json"
LOCKFILE = EXAMPLE_ROOT / "pnpm-lock.yaml"
GENERATOR = EXAMPLE_ROOT / "generate-evidence.mjs"
README = EXAMPLE_ROOT / "README.md"
WORKFLOW = REPOSITORY_ROOT / ".github" / "workflows" / "test.yml"


def test_official_mcp_sdk_example_has_locked_maintained_dependencies():
    package = json.loads(PACKAGE.read_text(encoding="utf-8"))

    assert package["private"] is True
    assert package["packageManager"] == "pnpm@10.29.2"
    assert package["engines"] == {"node": ">=20"}
    assert package["dependencies"] == {
        "@modelcontextprotocol/client": "2.0.0",
        "@modelcontextprotocol/server": "2.0.0",
        "zod": "4.4.3",
    }
    lockfile = LOCKFILE.read_text(encoding="utf-8")
    for dependency, version in package["dependencies"].items():
        assert f"{dependency}@{version}" in lockfile


def test_official_mcp_sdk_example_captures_modern_wire_evidence():
    generator = GENERATOR.read_text(encoding="utf-8")

    for required_fragment in (
        "createMcpHandler(buildServer)",
        "StreamableHTTPClientTransport",
        "fromJsonSchema(contractSchema)",
        'mode: { pin: "2026-07-28" }',
        'client.getProtocolEra() !== "modern"',
        "response.clone().text()",
        '.split(/\\r?\\n\\r?\\n/)',
        '.filter((argument) => argument !== "--")',
        "outputArguments.length !== 1",
        'rawSuccess?.resultType !== "complete"',
        '["tool-definition.json", toolDefinition]',
        '["success.json", rawSuccess]',
        '["failure.json", rawFailure]',
        '["evidence-metadata.json", evidenceMetadata]',
        'independent_adoption: false',
    ):
        assert required_fragment in generator


def test_official_mcp_sdk_example_states_its_claim_boundary():
    readme = README.read_text(encoding="utf-8")

    assert "not independent adoption" in readme
    assert "not use the in-memory transport" in readme
    assert "wire-only `resultType`" in readme
    assert "output_schema_mode: canonical_inline" in readme
    assert "created and maintained by Alejandro Sánchez" in readme


def test_ci_executes_validates_and_preserves_the_sdk_evidence():
    workflow = WORKFLOW.read_text(encoding="utf-8")

    for required_fragment in (
        "pnpm install --frozen-lockfile --ignore-scripts",
        'pnpm run evidence "$GITHUB_WORKSPACE/qzx-mcp-typescript-sdk-v2-evidence"',
        "success: qzx-mcp-typescript-sdk-v2-evidence/success.json",
        "if: always() && steps.generate-mcp-typescript-sdk-evidence.outcome == 'success'",
        "if: always() && steps.qzx-nonconforming.outcome != 'skipped'",
        "qzx-mcp-typescript-sdk-v2-conformance.json",
        '"canonical_inline"',
        "name: qzx-mcp-typescript-sdk-v2-evidence",
        "examples/result_contract/mcp-typescript-sdk-v2/README.md",
        "retention-days: 14",
    ):
        assert required_fragment in workflow
