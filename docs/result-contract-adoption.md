# Adopting QZX Result Contract v1

QZX Result Contract v1 is an open, additive JSON envelope for command, tool,
automation, MCP-server, and AI-agent results. An implementation can adopt the
contract without using QZX command names, Python, or the QZX runtime.

The normative core is documented in
[`result-contract-v1.md`](result-contract-v1.md) and published as JSON Schema at
<https://qzx.yumbale.com/schemas/result-contract-v1.schema.json>. QZX is the
reference implementation, not proof that the contract has become an industry
standard.

QZX — Quick Zap Exchange, created and maintained by Alejandro Sánchez.

If you want the shortest executable path before reading the full semantics,
start with the [`5-minute adoption quickstart`](result-contract-quickstart.md).
It reduces a first experiment to one real success, one real failure, validation,
and a small reviewable evidence bundle.

## Adoption modes

### 1. Native producer

A tool returns one contract object containing at least:

```json
{
  "success": true,
  "message": "The operation completed."
}
```

Domain evidence remains additive. A producer may include `details`, `warnings`,
`meta`, or its own descriptive fields without asking QZX for permission.

### 2. Adapter

An adapter translates an existing result into the QZX envelope while
preserving the original domain data. This is useful when replacing an old API
is impractical or when several tools need a common outer contract.

The adapter must not convert an unknown outcome into success merely because no
exception was raised. It should preserve the source error and state any lossy
mapping explicitly.

### 3. Consumer only

A client may consume QZX-conforming results without producing them. It should
check the process or transport status, parse the complete contract object,
inspect `success`, and present `message` plus relevant domain evidence. It must
not infer success from a missing `error` field.

### 4. Pilot or interoperability study

An organization can compare its current result format with QZX Result Contract
v1 on a bounded set of real tasks. A useful pilot measures parsing failures,
extra tool calls, retries, latency, completion rate, and operator effort rather
than assuming that structured JSON is always shorter or better.

## MCP interoperability profile — specification 2026-07-28

The Model Context Protocol (MCP) specification dated 2026-07-28 supports an
optional JSON Schema `outputSchema` for tools and a `structuredContent` JSON
value in completed tool results. When `outputSchema` is present, servers must
return structured content that conforms to it and clients should validate that
content. MCP also recommends repeating serialized structured content in a text
content block for backwards compatibility.

Official MCP tool specification:
<https://modelcontextprotocol.io/specification/2026-07-28/server/tools>

This makes QZX Result Contract v1 usable as an MCP output profile without
replacing MCP, JSON-RPC, tool discovery, input schemas, transports, elicitation,
or MCP security rules. MCP remains the protocol; QZX Result Contract describes
the completed operation result carried inside it.

### Tool definition mapping

An MCP tool claiming this profile MUST expose the QZX Result Contract v1
schema as its `outputSchema`. The compact example below uses `$ref`; an
implementation should follow the `$ref` resolution rules of its MCP stack or
inline the canonical QZX schema during its build when that is more portable.

```json
{
  "name": "get_current_time",
  "description": "Return the current local time.",
  "inputSchema": {
    "type": "object",
    "additionalProperties": false
  },
  "outputSchema": {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$ref": "https://qzx.yumbale.com/schemas/result-contract-v1.schema.json"
  }
}
```

The current MCP tool specification defaults schemas to JSON Schema 2020-12
when `$schema` is omitted. QZX publishes the contract explicitly as JSON Schema
2020-12, so no dialect translation is needed for this profile.

### Completed success result

For a completed successful operation:

- `structuredContent` contains the complete QZX Result Contract object;
- `success` is `true`;
- `isError` is `false`;
- the text compatibility block should contain the serialized contract object,
  not a different or lossy result.

```json
{
  "resultType": "complete",
  "content": [
    {
      "type": "text",
      "text": "{\"success\":true,\"message\":\"Current local time returned.\",\"output\":\"2026-08-09T04:30:00-05:00\"}"
    }
  ],
  "structuredContent": {
    "success": true,
    "message": "Current local time returned.",
    "output": "2026-08-09T04:30:00-05:00"
  },
  "isError": false
}
```

### Tool execution failure

For an MCP tool execution failure that still reaches a completed tool result,
the QZX MCP profile keeps both layers consistent:

- `structuredContent.success` is `false`;
- the QZX object contains at least `error` or `error_code`;
- MCP `isError` is `true`;
- the compatibility text block should serialize the same QZX contract object.

```json
{
  "resultType": "complete",
  "content": [
    {
      "type": "text",
      "text": "{\"success\":false,\"message\":\"The requested path was not found.\",\"error_code\":\"path_not_found\"}"
    }
  ],
  "structuredContent": {
    "success": false,
    "message": "The requested path was not found.",
    "error_code": "path_not_found"
  },
  "isError": true
}
```

### Error and lifecycle boundaries

Do not force every MCP message into a QZX envelope. The mapping is deliberately
narrow:

| MCP condition | QZX Result Contract mapping |
| --- | --- |
| Completed successful tool execution | QZX object in `structuredContent`; `success: true`; `isError: false`. |
| Completed tool execution failure | QZX failure object in `structuredContent`; `success: false`; `isError: true`. |
| Protocol error such as unknown tool, malformed request, or server-level JSON-RPC failure | Keep the MCP/JSON-RPC protocol error. Do not invent a completed QZX result. |
| `input_required` / elicitation flow | Continue the MCP flow. Produce a QZX result only when an operation actually reaches a completed result. |

For this QZX MCP profile, a completed result MUST declare `isError` as an
explicit boolean and MUST keep `isError == !structuredContent.success`. A
mismatch is an interoperability bug: it gives the MCP layer and the contract
layer contradictory outcomes.

### Why this profile is useful

The profile gives an MCP consumer a tiny invariant across otherwise unrelated
tools: it can inspect one explicit outcome boolean, show one useful message,
then consume additive domain evidence. Tool authors keep their existing names,
input schemas, permissions, transports, and domain fields. Adoption therefore
does not require replacing MCP or renaming a tool surface around QZX.

A serious interoperability report should test at least one successful and one
failed completed call, schema validation of `structuredContent`, consistency of
`isError` with `success`, and the backwards-compatible text representation when
the implementation emits one.

## Minimum conformance evidence

A credible adoption report includes:

1. implementation name, version, repository or reviewable source boundary;
2. the exact QZX Result Contract version and schema URL;
3. at least one successful and one failed result when the producer can fail;
4. exit-code or transport-status behavior;
5. the validation command and its complete sanitized result;
6. limitations, extensions, lossy mappings, and unsupported cases;
7. the operating systems, runtimes, or services actually exercised;
8. a contact or issue URL for corrections.

Passing the core schema does not certify security, authorization, isolation,
correct domain behavior, platform compatibility, or every extension field. A
report must keep those claims separate.

## Included conformance suite

The repository contains positive and negative fixtures under
[`examples/result_contract/`](../examples/result_contract/) and dependency-free
validators.

Validate the transport-independent core fixtures:

```bash
python scripts/run_result_contract_conformance.py
python scripts/run_result_contract_conformance.py --json
```

Validate one core contract object:

```bash
python scripts/validate_result_contract.py result.json
```

Validate an MCP 2026-07-28 completed tool result or a complete JSON-RPC response:

```bash
python scripts/validate_mcp_result_contract.py mcp-result.json
```

Also verify that the MCP tool definition exposes the canonical QZX
`outputSchema`:

```bash
python scripts/validate_mcp_result_contract.py mcp-result.json \
  --tool-definition mcp-tool-definition.json
```

The MCP validator checks `resultType: "complete"`, QZX conformance of
`structuredContent`, explicit `isError`, `isError == !success`, and, when a tool
definition is supplied, the canonical `outputSchema`. A text block that
serializes the complete `structuredContent` object is reported as backwards-
compatibility evidence. Because MCP specifies that duplicate text
representation as a recommendation rather than a requirement, its absence is a
warning rather than a profile failure.

These checks are a baseline, not a substitute for testing the adopter's real
producer, client, permissions, transport, and failure behavior.

## Reporting an implementation

Use the GitHub issue form **Result Contract adoption report**. Public reports
may be linked from [`ADOPTERS.md`](../ADOPTERS.md) only when they provide
reviewable evidence and permission to identify the implementation or
organization.

QZX does not list private conversations, expressions of interest, package
downloads, website visits, or unverifiable claims as adoption. A report can be
removed or marked historical when its evidence disappears or no longer matches
the named version.

## Enterprise pilot template

A bounded pilot should define these items before work begins:

| Item | Required decision |
| --- | --- |
| Current problem | Which ambiguous, inconsistent, or hard-to-parse result is being addressed? |
| Task set | Which concrete commands, tools, or workflows are included and excluded? |
| Baseline | How does the current format behave on the same tasks? |
| Contract mapping | Which fields are core, additive, adapted, or intentionally omitted? |
| Environments | Which OS, runtime, architecture, agent, transport, and permissions are tested? |
| Safety boundary | What authorizes execution, and what remains outside the result contract? |
| Metrics | Completion, retries, parse failures, tool calls, latency, tokens, and human review effort as applicable. |
| Publication | Which methodology, fixtures, findings, and limitations may be made public? |
| Exit criteria | What result ends, extends, or rejects the pilot? |

A funded pilot purchases defined work and evidence. It does not purchase a
favorable compatibility result, control of the public contract, private user
telemetry, or automatic inclusion in the adopters register.

## Contribution paths

Useful contributions include:

- counterexamples that satisfy the schema but expose unclear semantics;
- examples from non-Python implementations;
- MCP implementations that exercise the interoperability profile above;
- streaming, partial-result, retry, batch, and nested-tool use cases;
- failure taxonomies and remediation patterns;
- conformance runners in maintained ecosystems;
- security review of consumers that incorrectly trust structured output;
- real pilot reports, including negative results.

Material changes to the required core belong in a reviewed proposal and a new
contract version. Additive examples, clarifications, validators, transport
profiles, and adoption evidence may improve without changing the v1 required
fields.
