# QZX Result Contract v1

QZX Result Contract v1 is an open, additive JSON result envelope for commands
used by people, automation, and AI agents. It defines the small core a consumer
can rely on while allowing each operation to add the evidence it actually
needs.

The canonical machine-readable schema is:

- <https://qzx.yumbale.com/schemas/result-contract-v1.schema.json>
- `src/qzx/resources/schemas/result-contract-v1.schema.json` in the source tree
  and installed package.

QZX — Quick Zap Exchange, created and maintained by Alejandro Sánchez.

## Status

Version 1 is the first published contract. It is an open QZX specification, not
a claim that an external standards body or the wider industry has adopted it.
Other tools may implement it without using the QZX command vocabulary or QZX
runtime, subject to the project license and trademark policy.

A producer may describe a completed result as **QZX Result Contract v1
compatible** when the contract object satisfies the machine-readable schema and
the applicable normative requirements below. Compatibility does not imply
endorsement, certification, complete command parity, or permission to use the
QZX name as the producer's product name.

## Normative language and conformance

When the uppercase requirement terms `MUST`, `MUST NOT`, `SHOULD`, `SHOULD NOT`,
`MAY`, and `OPTIONAL` appear in this document, interpret them according to BCP
14 (RFC 2119 and RFC 8174). Lowercase uses keep their ordinary English meaning.

- The JSON Schema is normative for the machine-checkable shape of a QZX Result
  Contract v1 object.
- This document is normative for semantics that cannot be expressed completely
  by the schema.
- **Core producer conformance is transport-independent.** A CLI, MCP server,
  HTTP API, library, build tool, or adapter may carry the same contract object
  through different transports.
- A transport profile MAY add requirements around framing, process exit status,
  protocol error signaling, or compatibility payloads, but it MUST NOT redefine
  the meaning or type of the v1 core fields.

## Stable core

Every completed result is one JSON object containing:

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `success` | boolean | yes | `true` only when the requested operation completed successfully. |
| `message` | non-empty string | yes | Complete human-readable summary of the outcome. It must contain at least one non-whitespace character. |
| `error` | non-empty string | on failure when no `error_code` exists | Human-readable failure description containing at least one non-whitespace character. |
| `error_code` | lower_snake_case string | on failure when no `error` exists | Stable machine-oriented failure identifier. |
| `details` | object | no | Structured diagnostics, remediation, or domain-specific context. |
| `warnings` | array of non-empty strings | no | Non-fatal conditions that deserve explicit attention; each item must contain at least one non-whitespace character. |
| `meta` | object | no | Shared invocation metadata, including schema version, command, duration, and maturity when available. |

When `meta.command` is present, it must contain at least one non-whitespace
character. A failed result MUST contain at least `error` or `error_code`. A
successful result MUST NOT contain either failure field; non-fatal conditions
belong in `warnings` or domain-specific evidence instead. Defined optional core
fields and defined `meta` fields MUST satisfy their declared type when present;
`null` is not a substitute for omitting an unavailable field. Producers MAY add
command-specific top-level fields and additional metadata. Consumers MUST ignore
unknown fields unless a command-specific contract says otherwise.

## Successful example

```json
{
  "success": true,
  "message": "Current local date and time returned in ISO 8601 format.",
  "output": "2026-08-07T21:45:00-05:00",
  "meta": {
    "command": "getCurrentDateTime",
    "duration_ms": 2.4,
    "schema_version": 1
  }
}
```

## Failed example

```json
{
  "success": false,
  "message": "The requested path was not found.",
  "error": "Path not found: missing.txt",
  "error_code": "path_not_found",
  "details": {
    "path": "missing.txt"
  },
  "meta": {
    "command": "readFile",
    "duration_ms": 1.1,
    "schema_version": 1
  }
}
```

## Core producer requirements

1. A producer MUST provide exactly one QZX Result Contract object for each
   completed operation result. A surrounding protocol MAY wrap that object in
   its own result structure.
2. A producer MUST emit an explicit boolean `success`; consumers must never
   need to infer success from the presence or absence of another field.
3. `message` MUST be useful as a standalone summary and MUST contain at least
   one non-whitespace character.
4. A failed result MUST contain at least one of `error` or `error_code`.
5. A successful result MUST NOT contain `error` or `error_code`.
6. Defined optional core fields and defined `meta` fields MUST satisfy their
   declared type when present; an unavailable defined field is omitted rather
   than represented by `null`.
7. A producer SHOULD use stable `error_code` values for failures on which a
   consumer may branch programmatically.
8. Command-specific evidence MUST be truthful and typed. A producer MUST NOT
   invent values for information it could not obtain.
9. Additive fields MAY evolve compatibly. Removing a required field, changing
   its type, or changing its meaning requires a new contract version.

## Core consumer requirements

1. A consumer MUST parse the complete contract object before interpreting
   command-specific fields.
2. A consumer MUST inspect `success` before deciding whether domain-specific
   output represents a successful operation.
3. A consumer SHOULD present `message` when a human needs a concise explanation
   of the outcome.
4. A consumer SHOULD prefer `error_code` for stable programmatic handling and
   `error` for diagnostic context.
5. A consumer relaying a result SHOULD preserve unknown fields and MUST NOT
   reject a valid v1 result merely because additive fields are unfamiliar.
6. A consumer MUST NOT treat contract compatibility as proof that an operation
   is safe, authorized, sandboxed, correct for its domain, or available on every
   platform.

## Layering with protocol-native status and errors

QZX Result Contract describes a **completed operation result**. It does not
replace the status and error mechanisms of the transport carrying that result.
HTTP status codes and problem-detail documents, JSON-RPC errors, MCP protocol
errors, process exit statuses, and application-specific error models may all
remain appropriate at their own layer.

The explicit `success` field serves a different purpose: it travels with the
operation result itself. If that object is logged, cached, queued, stored,
replayed, or passed through another transport without its original wrapper, its
outcome remains self-describing. A transport profile MAY therefore duplicate
the outcome in native metadata, but it MUST define a consistent mapping rather
than create a competing meaning.

A malformed request, unknown protocol method, framing failure, or comparable
transport/protocol error MUST NOT be fabricated as a completed QZX Result
Contract merely to force every failure into one envelope. Only once an
operation has a completed result does the QZX core apply.

## QZX CLI JSON transport profile

The core contract does not require `stdout`, `stderr`, or a process exit code.
Those are transport concerns. A CLI that claims the **QZX CLI JSON transport
profile** has these additional requirements:

1. Machine-output mode MUST write exactly one complete QZX Result Contract JSON
   document to `stdout`, with no leading or trailing non-JSON output.
2. Progress, diagnostics, and incidental native output MUST go to `stderr` or
   another channel that cannot corrupt the JSON document.
3. The process exit status SHOULD agree with the contract outcome. The v1 core
   does not assign universal numeric exit codes to domain failures.

QZX itself implements this profile when `--json` is requested.

## Validation

Validate a saved result from a source checkout:

```bash
python scripts/validate_result_contract.py result.json
python scripts/validate_result_contract.py result.json --json
```

Validate a live QZX CLI result without an intermediate file:

```bash
qzx getCurrentDateTime --output-format iso --json \
  | python scripts/validate_result_contract.py -
```

The validator has no third-party runtime dependency. The QZX CLI also validates
its own final envelope before printing it; invalid internal producer output is
replaced with a conforming `invalid_result_contract` failure instead of leaking
an ambiguous document.

The public validation tools decode evidence conservatively for cross-language
interoperability. They reject duplicate object member names, the non-JSON
numeric tokens `NaN` and `Infinity`, and numbers outside the decoder's finite
range. This follows [RFC 8259](https://www.rfc-editor.org/rfc/rfc8259): duplicate
names can produce unpredictable mappings across implementations, while
non-finite numeric tokens are not JSON.

The public conformance fixtures include both valid documents and documents that
MUST be rejected, including a whitespace-only `message`, a successful result
with a contradictory `error_code`, and a defined typed field set to `null`.

## Compatibility and evolution

Version 1 is intentionally small. Command-specific fields remain outside this
shared schema because a disk inspection, file search, DNS query, and process
operation require different evidence.

Compatible evolution may:

- add optional fields;
- add new `error_code` values;
- add command-specific objects;
- add metadata fields;
- add transport profiles that preserve the core semantics;
- strengthen documentation or machine-readable constraints so they match the
  already-defined field meaning.

A new major contract version is required to:

- remove or rename a required field;
- change the type or meaning of `success` or `message`;
- change the root contract away from one JSON object per completed result;
- make a currently optional core field mandatory for all producers;
- redefine failure semantics incompatibly.

## Review and adoption

Technical review, independent implementations, conformance reports, and
well-scoped pilots are welcome. Open an issue in the QZX repository or contact
`qzx@yumbale.com`. Organizations may sponsor public conformance work,
compatibility testing, documentation, or integrations without purchasing
control of the open specification or access to private telemetry.
