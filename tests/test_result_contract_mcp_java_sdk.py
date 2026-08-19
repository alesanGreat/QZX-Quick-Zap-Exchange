#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Regression tests for the official MCP Java SDK interoperability example."""

from __future__ import annotations

from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_ROOT = (
    REPOSITORY_ROOT / "examples" / "result_contract" / "mcp-java-sdk-v2"
)
POM = EXAMPLE_ROOT / "pom.xml"
DEPENDENCY_TREE = EXAMPLE_ROOT / "dependency-tree.txt"
GENERATOR = EXAMPLE_ROOT / "src" / "main" / "java" / "qzx" / "evidence" / "Main.java"
WRAPPER_PROPERTIES = EXAMPLE_ROOT / ".mvn" / "wrapper" / "maven-wrapper.properties"
MAVEN_WRAPPER = EXAMPLE_ROOT / "mvnw"
WINDOWS_MAVEN_WRAPPER = EXAMPLE_ROOT / "mvnw.cmd"
README = EXAMPLE_ROOT / "README.md"
EXAMPLES_INDEX = REPOSITORY_ROOT / "examples" / "result_contract" / "README.md"
WORKFLOW = REPOSITORY_ROOT / ".github" / "workflows" / "test.yml"
DEPENDABOT = REPOSITORY_ROOT / ".github" / "dependabot.yml"
MANIFEST = REPOSITORY_ROOT / "MANIFEST.in"


def test_official_mcp_java_sdk_example_locks_sdk_maven_and_dependencies():
    pom = POM.read_text(encoding="utf-8")
    for required_fragment in (
        "<maven.compiler.release>17</maven.compiler.release>",
        "<artifactId>mcp</artifactId>",
        "<version>2.0.0</version>",
        "<artifactId>slf4j-nop</artifactId>",
        "<version>2.0.16</version>",
        "<directory>${qzx.build.directory}</directory>",
        "<artifactId>spring-javaformat-maven-plugin</artifactId>",
        "<goal>validate</goal>",
        "<arg>-Xlint:all</arg>",
        "<arg>-Werror</arg>",
    ):
        assert required_fragment in pom

    wrapper = WRAPPER_PROPERTIES.read_text(encoding="utf-8")
    assert "wrapperVersion=3.3.4" in wrapper
    assert "apache-maven-3.9.9-bin.zip" in wrapper
    assert (
        "distributionSha256Sum="
        "4ec3f26fb1a692473aea0235c300bd20f0f9fe741947c82c1234cefd76ac3a3c"
        in wrapper
    )
    assert MAVEN_WRAPPER.is_file()
    assert WINDOWS_MAVEN_WRAPPER.is_file()

    dependency_tree = DEPENDENCY_TREE.read_text(encoding="utf-8")
    assert "io.modelcontextprotocol.sdk:mcp:jar:2.0.0:compile" in dependency_tree
    assert "tools.jackson.core:jackson-databind:jar:3.0.3:compile" in dependency_tree
    assert "org.slf4j:slf4j-nop:jar:2.0.16:runtime" in dependency_tree


def test_official_mcp_java_sdk_example_uses_real_subprocess_stdio_transport():
    generator = GENERATOR.read_text(encoding="utf-8")

    for required_fragment in (
        'PROTOCOL_VERSION = "2025-11-25"',
        "new StdioServerTransportProvider(JSON)",
        "McpServer.sync(transport)",
        ".outputSchema(schema)",
        "ServerParameters.builder(javaCommand())",
        "new StdioClientTransport(parameters, JSON)",
        "client.initialize()",
        "client.listTools()",
        "client.callTool(",
        '"1207f0fcd064467801f5c7791d73a0d41266ec4158547abe595ef6e10b11f869"',
        '"2b96692e5b4edbfa63fa687050ba697f9070b9d1c49f3e054473c6b2da6c03ed"',
        '"e224c9ebea46fbbf75d32194fbb4897dd65859b0ca4deb4cbcf2383dc3a9289a"',
        'metadata.put("contract_evidence_sha256", evidenceSha256)',
        'metadata.put("jsonrpc_framing_exercised", true)',
        'metadata.put("wire_capture_retained", false)',
        'metadata.put("independent_adoption", false)',
    ):
        assert required_fragment in generator


def test_official_mcp_java_sdk_example_states_its_claim_boundary():
    readme = README.read_text(encoding="utf-8")

    assert "not independent adoption" in readme
    assert "does not exercise HTTP\nor SSE" in readme
    assert "does not retain raw frames" in readme
    assert "output_schema_mode: canonical_inline" in readme
    assert "not a claim that every JAR digest is recorded" in readme
    assert "created and maintained by Alejandro Sánchez" in readme


def test_result_contract_examples_index_exposes_the_java_sdk_boundary():
    index = EXAMPLES_INDEX.read_text(encoding="utf-8")

    assert "[Java SDK v2](mcp-java-sdk-v2/README.md)" in index
    assert "MCP 2025-11-25" in index
    assert "Subprocess `stdio` with newline-delimited JSON-RPC" in index
    assert "All five run real official client/server" in index


def test_ci_executes_validates_and_preserves_the_java_sdk_evidence():
    workflow = WORKFLOW.read_text(encoding="utf-8")

    for required_fragment in (
        "actions/setup-java@b6effb05e454b25005698d916606bdc6ffcbf961",
        'java-version: "21"',
        "mcp-java-sdk-v2/dependency-tree.txt",
        '"-Dqzx.build.directory=$artifacts"',
        "clean compile dependency:build-classpath",
        "actual != expected",
        "qzx.evidence.Main",
        "profile: mcp-2025-11-25",
        "success: qzx-mcp-java-sdk-v2.0.0-evidence/success.json",
        "qzx-mcp-java-sdk-v2.0.0-conformance.json",
        "name: qzx-mcp-java-sdk-v2.0.0-evidence",
        "examples/result_contract/mcp-java-sdk-v2/src/main/java/qzx/evidence/Main.java",
        "include-hidden-files: true",
        "retention-days: 14",
    ):
        assert required_fragment in workflow

    dependabot = DEPENDABOT.read_text(encoding="utf-8")
    assert 'package-ecosystem: "maven"' in dependabot
    assert 'directory: "/examples/result_contract/mcp-java-sdk-v2"' in dependabot
    assert '"io.modelcontextprotocol.sdk:*"' in dependabot

    manifest = MANIFEST.read_text(encoding="utf-8")
    assert "*.java *.xml *.properties *.cmd mvnw" in manifest
