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

A producer may describe its output as **QZX Result Contract v1 compatible** when
all emitted JSON results satisfy the rules below. Compatibility does not imply
endorsement, certification, complete command parity, or permission to use the
QZX name as the producer's product name.

## Stable core

Every result is one JSON object containing:

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `success` | boolean | yes | `true` only when the requested operation completed successfully. |
| `message` | non-empty string | yes | Complete human-readable summary of the outcome. |
| `error` | non-empty string | on failure when no `error_code` exists | Human-readable failure description. |
| `error_code` | lower_snake_case string | on failure when no `error` exists | Stable machine-oriented failure identifier. |
| `details` | object | no | Structured diagnostics, remediation, or domain-specific context. |
| `warnings` | array of non-empty strings | no | Non-fatal conditions that deserve explicit attention. |
| `meta` | object | no | Shared invocation metadata, including schema version, command, duration, and maturity when available. |

A failed result must contain at least `error` or `error_code`. Producers may add
command-specific top-level fields and additional metadata. Consumers must ignore
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

## Producer rules

1. Write exactly one JSON document to `stdout` in machine-output mode.
2. Send progress, diagnostics, and incidental native output to `stderr`.
3. Never infer success from an empty error field: emit an explicit boolean.
4. Make `message` useful without requiring the consumer to reconstruct it from
   command-specific fields.
5. Use stable `error_code` values for failures a consumer may branch on.
6. Keep command-specific evidence truthful and typed; do not fill unavailable
   fields with invented values.
7. Add fields compatibly. Removing a required field, changing its type, or
   changing its meaning requires a new contract version.

## Consumer rules

1. Parse one complete JSON object and reject trailing non-JSON output.
2. Read `success` before interpreting domain-specific fields.
3. Present `message` when a human needs a concise explanation.
4. Use `error_code` for stable programmatic handling and `error` for diagnostic
   context.
5. Preserve unknown fields when relaying a result and ignore them when they are
   not understood.
6. Do not treat contract compatibility as proof that an operation is safe,
   authorized, sandboxed, or available on every platform.

## Validation

Validate a saved result from a source checkout:

```bash
python scripts/validate_result_contract.py result.json
python scripts/validate_result_contract.py result.json --json
```

Validate a live QZX command without an intermediate file:

```bash
qzx getCurrentDateTime --output-format iso --json \
  | python scripts/validate_result_contract.py -
```

The validator has no third-party runtime dependency. The QZX CLI also validates
its own final envelope before printing it; invalid internal producer output is
replaced with a conforming `invalid_result_contract` failure instead of leaking
an ambiguous document.

## Compatibility and evolution

Version 1 is intentionally small. Command-specific fields remain outside this
shared schema because a disk inspection, file search, DNS query, and process
operation require different evidence.

Compatible evolution may:

- add optional fields;
- add new `error_code` values;
- add command-specific objects;
- add metadata fields;
- strengthen documentation without changing field meaning.

A new major contract version is required to:

- remove or rename a required field;
- change the type or meaning of `success` or `message`;
- permit multiple documents on `stdout`;
- make a currently optional core field mandatory for all producers;
- redefine failure semantics incompatibly.

## Review and adoption

Technical review, independent implementations, conformance reports, and
well-scoped pilots are welcome. Open an issue in the QZX repository or contact
`qzx@yumbale.com`. Organizations may sponsor public conformance work,
compatibility testing, documentation, or integrations without purchasing
control of the open specification or access to private telemetry.
