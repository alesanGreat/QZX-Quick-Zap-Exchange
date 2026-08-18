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
| `invalid-success-with-error-code.json` | Rejected: successful result carries a contradictory failure identifier. |
| `invalid-null-details.json` | Rejected: defined optional core field uses `null` instead of its declared type. |

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
object in `structuredContent`, keep MCP `isError` consistent with `!success`,
and expose the strongest truthful `outputSchema` your SDK can publish. Use the
canonical QZX schema directly or through `allOf` when supported; object-schema-
only SDKs can expose the constrained QZX core and receive the explicitly weaker
`structural_core` evidence mode.

## MCP structured-output profile fixtures

QZX supports revision-specific MCP profiles for 2025-06-18, 2025-11-25, and
2026-07-28. The repository now includes both historical 2025 wire evidence
without `resultType` and 2026-07-28 evidence with `resultType: "complete"`, so an
adopter does not need to edit a newer fixture to simulate an older server.

For an executable MCP 2026-07-28 integration rather than static fixtures, use
the locked [official TypeScript SDK v2 example](mcp-typescript-sdk-v2/README.md).
It runs a real client/server success and failure pair, captures the wire results,
and is continuously checked in CI. It remains QZX-maintained reference evidence,
not independent adoption.

| File | Purpose |
| --- | --- |
| `mcp-tool-definition.json` | Strong `canonical_ref` tool definition using QZX Result Contract v1 as `outputSchema`. |
| `mcp-structural-tool-definition.json` | SDK-portable `structural_core` tool definition that keeps a domain-shaped object schema. |
| `mcp-2025-success.json` | Completed 2025-06-18/2025-11-25 success result with no `resultType`. |
| `mcp-2025-failure.json` | Completed 2025-06-18/2025-11-25 tool-execution failure with no `resultType`. |
| `mcp-success.json` | Completed MCP 2026-07-28 success with `resultType: "complete"`. |
| `mcp-failure.json` | Completed MCP 2026-07-28 tool-execution failure with `isError: true`. |
| `mcp-invalid-is-error.json` | Deliberate contradiction between MCP `isError` and QZX `success`. |
| `mcp-protocol-error.json` | JSON-RPC protocol error that must remain outside a completed QZX result. |

Validate the portable 2025 case exactly as a maintained object-schema-only MCP
SDK might expose it:

```bash
python scripts/validate_result_contract_evidence.py \
  --profile mcp-2025-11-25 \
  --success examples/result_contract/mcp-2025-success.json \
  --failure examples/result_contract/mcp-2025-failure.json \
  --tool-definition examples/result_contract/mcp-structural-tool-definition.json \
  --report qzx-conformance.json
```

That receipt reports `output_schema_mode: structural_core`; it does not pretend
the canonical QZX schema is embedded in `outputSchema`. To exercise the stronger
2026 canonical-reference path instead:

```bash
python scripts/validate_result_contract_evidence.py \
  --profile mcp-2026-07-28 \
  --success examples/result_contract/mcp-success.json \
  --failure examples/result_contract/mcp-failure.json \
  --tool-definition examples/result_contract/mcp-tool-definition.json \
  --report qzx-conformance.json
```

The receipt records SHA-256 digests of the exact evidence files and fingerprints
the exact QZX contract schema, receipt schema, core validator, MCP validator,
and evidence validator used for the verdict. It preserves validator warnings
and profile facts and self-identifies the public
`result-contract-conformance-receipt-v1.schema.json` schema, so reviewers can
validate the receipt structure independently with JSON Schema 2020-12. A valid
receipt schema does not imply a passing conformance result. External GitHub
repositories can run the same check with the reusable repository-root
`action.yml`, using the normal `owner/repository@sha` form.

Then replace the fixtures with output from **one real tool**. The quickest path
to a reviewable independent experiment is documented in
[`../../docs/result-contract-quickstart.md`](../../docs/result-contract-quickstart.md).

Passing these validators proves only the named result/profile invariants. It
does not certify security, authorization, domain correctness, platform
compatibility, or endorsement by QZX.
