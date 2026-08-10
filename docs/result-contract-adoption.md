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

## MCP interoperability profiles — 2025-06-18 through 2026-07-28

MCP already supported tool `outputSchema`, `structuredContent`, explicit
`isError`, and the protocol-error/tool-execution-error boundary in specification
2025-06-18. Those structured-output semantics remain available in 2025-11-25
and 2026-07-28. QZX therefore defines revision-specific profiles for all three
revisions instead of forcing an otherwise-compatible producer to upgrade its
entire MCP stack merely to claim Result Contract interoperability.

Official MCP tool specifications:

- <https://modelcontextprotocol.io/specification/2025-06-18/server/tools>
- <https://modelcontextprotocol.io/specification/2025-11-25/server/tools>
- <https://modelcontextprotocol.io/specification/2026-07-28/server/tools>

The common QZX mapping is the same: the complete QZX object is carried in
`structuredContent`, MCP `isError` agrees with `!structuredContent.success`, and
the tool's `outputSchema` makes the stable QZX core fields reviewable. The
wire-level lifecycle is not falsely flattened across revisions: MCP 2026-07-28
requires `resultType: "complete"` for an ordinary completed result, while the
2025 profiles do not require a field those revisions did not define. MCP
2026-07-28 `input_required` is an interim protocol result and is not a completed
QZX Result Contract operation.

This makes QZX Result Contract v1 usable as an MCP output profile without
replacing MCP, JSON-RPC, tool discovery, input schemas, transports, elicitation,
or MCP security rules. MCP remains the protocol; QZX Result Contract describes
the completed operation result carried inside it.

### Tool definition mapping and schema strength

QZX deliberately records **how strongly** an MCP `outputSchema` exposes the
contract instead of pretending every SDK can publish the same JSON Schema
shape. A conformance receipt reports one of these modes:

| Mode | Meaning |
| --- | --- |
| `canonical_ref` | `outputSchema` directly references the canonical QZX Result Contract v1 schema. |
| `canonical_inline` | `outputSchema` is the exact canonical QZX schema inline. |
| `canonical_allof` | `outputSchema` composes the canonical QZX schema through `allOf`, allowing additional domain constraints. |
| `structural_core` | The MCP SDK exposes an object schema with the required QZX core fields and constraints; the submitted runtime evidence is validated separately against the complete Result Contract. |

The first three modes prove the canonical schema relationship from
`outputSchema` itself. `structural_core` is intentionally a weaker and explicit
claim: it exists for maintained MCP SDK APIs that accept object-shaped output
schemas but cannot portably publish a canonical `$ref`/`allOf` wrapper around an
existing typed domain schema. It does **not** mean that `outputSchema` alone
encodes every QZX invariant.

A direct canonical reference is the smallest strong form:

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

When a stack supports JSON Schema composition, preserve a precise domain schema
instead of throwing it away. For example:

```json
{
  "outputSchema": {
    "allOf": [
      {
        "$ref": "https://qzx.yumbale.com/schemas/result-contract-v1.schema.json"
      },
      {
        "type": "object",
        "properties": {
          "data": { "type": "object" }
        }
      }
    ]
  }
}
```

For `structural_core`, the schema must at minimum require boolean `success` and
a nonblank string `message`, and declare either a nonblank string `error` or a
canonical `error_code` field for failure evidence. The success/failure evidence
is still validated against the complete canonical QZX Result Contract v1
schema. This prevents SDK limitations from becoming adoption blockers without
silently weakening the published claim.

### Completed success result

The examples below show the MCP 2026-07-28 wire shape. For the 2025-06-18 and
2025-11-25 profiles, omit the `resultType` member; the QZX object,
`structuredContent`, `content`, and `isError` invariants remain the same.

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
| MCP 2026-07-28 `input_required` flow | Continue the MCP flow. Produce a QZX result only when an operation actually reaches `resultType: "complete"`. |

For every QZX MCP profile, a completed result MUST declare `isError` as an
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

When QZX's evidence CLI or Composite Action is used, publish the generated
`qzx-conformance.json` receipt and identify the full QZX commit SHA that ran the
validator. The receipt records SHA-256 digests of the exact success, failure,
and MCP tool-definition files when applicable. It also identifies the public
QZX Result Contract Conformance Receipt v1 schema at
`https://qzx.yumbale.com/schemas/result-contract-conformance-receipt-v1.schema.json`,
so a reviewer can validate the report structure independently of QZX code. The
receipt itself remains a valid QZX Result Contract v1 object; failed receipts
carry a stable `error_code`. A schema-valid receipt may still record a failed
conformance result; receipt structure and implementation conformance are
separate claims. An adopter may
instead use an independent JSON Schema or profile validator; QZX tooling is not
a dependency of the Result Contract itself.

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

Validate an MCP completed tool result or a complete JSON-RPC response. The
validator defaults to MCP 2026-07-28; select the producer's real revision when
validating older structured-output servers:

```bash
python scripts/validate_mcp_result_contract.py mcp-result.json

python scripts/validate_mcp_result_contract.py mcp-result.json \
  --spec-version 2025-11-25
```

Also verify that the MCP tool definition exposes the canonical QZX
`outputSchema`:

```bash
python scripts/validate_mcp_result_contract.py mcp-result.json \
  --spec-version 2025-11-25 \
  --tool-definition mcp-tool-definition.json
```

For independent evidence, validate the successful and failed completed results
together and write one deterministic receipt. Choose exactly one of
`mcp-2025-06-18`, `mcp-2025-11-25`, or `mcp-2026-07-28` to match the producer:

```bash
python scripts/validate_result_contract_evidence.py \
  --profile mcp-2025-11-25 \
  --success result-contract-evidence/success.json \
  --failure result-contract-evidence/failure.json \
  --tool-definition result-contract-evidence/tool-definition.json \
  --report result-contract-evidence/qzx-conformance.json
```

External GitHub repositories can execute the same pair check through the
reusable Composite Action in
[`.github/actions/result-contract-conformance`](../.github/actions/result-contract-conformance/action.yml).
The quickstart includes a copyable caller workflow. Pin the QZX Action to a full
commit SHA before publishing durable evidence.

Every MCP profile checks QZX conformance of `structuredContent`, explicit
`isError`, `isError == !success`, and, when a tool definition is supplied, the
canonical `outputSchema`. The MCP 2026-07-28 profile additionally checks
`resultType: "complete"`; the 2025 profiles do not require it. A text block that
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
