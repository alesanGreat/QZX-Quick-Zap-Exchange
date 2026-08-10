# QZX Result Contract examples

Copy these fixtures when evaluating **QZX Result Contract v1**. They are public
reference material, not evidence of independent adoption.

QZX — Quick Zap Exchange, created and maintained by Alejandro Sánchez.

## Core contract fixtures

| File | Expected result |
| --- | --- |
| `valid-success.json` | Conforming completed success. |
| `valid-failure.json` | Conforming completed failure with error evidence. |
| `invalid-missing-message.json` | Rejected: required `message` is missing. |
| `invalid-success-string.json` | Rejected: `success` is not a boolean. |
| `invalid-whitespace-message.json` | Rejected: whitespace-only `message`. |
| `invalid-failure-without-error.json` | Rejected: failed result has neither `error` nor `error_code`. |

Run all core cases:

```bash
python scripts/run_result_contract_conformance.py --json
```

Validate one document:

```bash
python scripts/validate_result_contract.py examples/result_contract/valid-success.json --json
```

`manifest.json` is the machine-readable inventory used by the conformance
runner.

## Minimal TypeScript producer

[`typescript-minimal.ts`](typescript-minimal.ts) shows how an existing
TypeScript tool can keep its domain-specific fields and add the small QZX
success/failure envelope without depending on the QZX runtime. The example uses
a discriminated union so failed results require a stable `error_code` at the
TypeScript type level.

The example is intentionally transport-neutral. For MCP, place the resulting
object in `structuredContent`, expose the canonical QZX schema as
`outputSchema`, and keep MCP `isError` consistent with `!success` as described
below.

## MCP structured-output profile fixtures

QZX supports revision-specific MCP profiles for 2025-06-18, 2025-11-25, and
2026-07-28. The checked-in fixtures use the 2026-07-28 wire shape and therefore
include `resultType: "complete"`. For a 2025 profile, real evidence may omit that
field; the `structuredContent`, `isError`, and `outputSchema` invariants remain.

| File | Purpose |
| --- | --- |
| `mcp-tool-definition.json` | Tool definition exposing QZX Result Contract v1 as `outputSchema`. |
| `mcp-success.json` | Completed successful MCP tool result. |
| `mcp-failure.json` | Completed failed MCP tool execution with `isError: true`. |
| `mcp-invalid-is-error.json` | Deliberate contradiction between MCP `isError` and QZX `success`. |
| `mcp-protocol-error.json` | JSON-RPC protocol error that must remain outside a completed QZX result. |

Validate the complete success/failure pair and tool definition, then write a
deterministic conformance receipt:

```bash
python scripts/validate_result_contract_evidence.py \
  --profile mcp-2026-07-28 \
  --success examples/result_contract/mcp-success.json \
  --failure examples/result_contract/mcp-failure.json \
  --tool-definition examples/result_contract/mcp-tool-definition.json \
  --report qzx-conformance.json
```

The receipt records SHA-256 digests of the exact evidence files and preserves
validator warnings and profile facts. It self-identifies the public
`result-contract-conformance-receipt-v1.schema.json` schema, so reviewers can
validate the receipt structure independently with JSON Schema 2020-12. A valid
receipt schema does not imply a passing conformance result. External GitHub
repositories can run the same check with the reusable Composite Action under
`.github/actions/result-contract-conformance`.

Then replace the fixtures with output from **one real tool**. The quickest path
to a reviewable independent experiment is documented in
[`../../docs/result-contract-quickstart.md`](../../docs/result-contract-quickstart.md).

Passing these validators proves only the named result/profile invariants. It
does not certify security, authorization, domain correctness, platform
compatibility, or endorsement by QZX.
