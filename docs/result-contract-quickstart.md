# QZX Result Contract v1 — 5-minute adoption quickstart

QZX Result Contract v1 is a small, additive result envelope. You do **not** need
to adopt QZX command names, use Python, replace your API, or turn your product
into QZX.

The smallest useful experiment is one real success result plus one real failure
result from a tool you already have.

QZX — Quick Zap Exchange, created and maintained by Alejandro Sánchez.

## 1. Add the two required fields

A successful operation starts with:

```json
{
  "success": true,
  "message": "The operation completed."
}
```

A failed completed operation starts with:

```json
{
  "success": false,
  "message": "The requested item was not found.",
  "error_code": "item_not_found"
}
```

Keep your existing domain data as additional fields. The contract is additive;
it does not require throwing useful evidence away. Successful results do not
carry `error` or `error_code`; use `warnings` for non-fatal conditions. When a
defined optional core or `meta` field is unavailable, omit it instead of
emitting `null` with the wrong type.

TypeScript producers can copy the dependency-free
[`typescript-minimal.ts`](../examples/result_contract/typescript-minimal.ts)
example. It models success/failure as a discriminated union while preserving
existing domain fields; it is an implementation example, not a substitute for
validating emitted JSON against the canonical schema.

Canonical JSON Schema:
<https://qzx.yumbale.com/schemas/result-contract-v1.schema.json>

## 2. Validate with your existing JSON Schema stack

If your language or framework already validates JSON Schema 2020-12, point it
at the canonical schema above. No QZX runtime dependency is required.

If you want to compare your implementation with the QZX reference validator,
clone the repository and run:

```bash
git clone --depth 1 https://github.com/alesanGreat/QZX-Quick-Zap-Exchange.git
cd QZX-Quick-Zap-Exchange
python scripts/validate_result_contract.py path/to/your-result.json
```

Exit status `0` means the document passes the QZX Result Contract v1 core
validator. A passing schema does not certify domain correctness, authorization,
security, or platform compatibility.

## 3. Validate the pair and produce a reviewable receipt

The conformance kit validates the semantic roles of both documents — the
success file must actually contain `success: true` and the failure file must
actually contain `success: false` — then records SHA-256 digests in a
deterministic JSON receipt:

```bash
python scripts/validate_result_contract_evidence.py \
  --profile core \
  --success result-contract-evidence/success.json \
  --failure result-contract-evidence/failure.json \
  --report result-contract-evidence/qzx-conformance.json
```

Evidence and MCP tool-definition files must use unique JSON object member
names. The evidence kit rejects duplicates before schema or profile validation
because JSON parsers may keep the first value, keep the last value, expose every
value, or reject the document. A file with both `"success": true` and
`"success": false` is therefore ambiguous evidence, even if one local parser
appears to accept it. This follows the interoperability guidance in
[RFC 8259 section 4](https://www.rfc-editor.org/rfc/rfc8259#section-4).
The same strict read rejects non-finite `NaN`, `Infinity`, and `-Infinity`
tokens, which JSON does not permit.

Every generated receipt identifies its own versioned JSON Schema at
`https://qzx.yumbale.com/schemas/result-contract-conformance-receipt-v1.schema.json`.
It also records SHA-256 digests for the exact QZX contract schema, receipt schema,
core validator, MCP validator, and evidence validator used to produce the
verdict. That makes a saved receipt independently traceable to the validation
materials even if a public `v1` URL later receives compatible clarifications.
Reviewers can validate the receipt structure with any JSON Schema 2020-12
implementation without executing QZX. The receipt itself also remains a valid
QZX Result Contract v1 object: failed receipts carry a stable `error_code`.
**Receipt schema validity is not an adoption verdict:** a structurally valid
receipt may intentionally record `success: false`, violations, unreadable
evidence, or a missing MCP tool definition.

For GitHub Actions, the repository also ships a reusable Composite Action at
its repository root. New callers can therefore use the normal
`owner/repository@sha` form without knowing QZX's internal directory layout. The
copyable workflow uses full commit SHAs so the executed code cannot move between
otherwise-identical runs and so it also works in repositories that enforce
SHA-pinned Actions:

```yaml
name: QZX Result Contract conformance
on:
  push:
    branches:
      - main
  pull_request:
  workflow_dispatch:

permissions:
  contents: read

jobs:
  qzx-result-contract:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7
        with:
          persist-credentials: false
      - id: qzx-conformance
        uses: alesangreat/QZX-Quick-Zap-Exchange@6a912448c7b2aa41c2a48923c355c422c02cd7a2
        with:
          profile: core
          success: result-contract-evidence/success.json
          failure: result-contract-evidence/failure.json
          report: result-contract-evidence/qzx-conformance.json
```

The QZX SHA above identifies the reviewed conformance implementation used by
this example; update it deliberately when you choose to validate against a
newer QZX revision. The Action fails the job when the pair does not conform and
writes the receipt path plus scalar `conformant`, `profile`, `receipt_schema`,
`contract_schema_sha256`, and `output_schema_mode` outputs for later workflow
steps. Its GitHub job summary keeps the PASS/FAIL result, the exact contract
schema digest, receipt metadata, the specification link, and factual creator
attribution together with the run.

### Preserve the receipt even when conformance fails

A failed conformance run is often the evidence a reviewer needs most. If you
want GitHub Actions to retain that receipt as a downloadable artifact, allow the
QZX step to finish as a recorded failure, upload the receipt unconditionally,
and then fail the job explicitly. This preserves the evidence **without turning
a failed conformance check into a passing gate**:

```yaml
      - id: qzx-conformance
        continue-on-error: true
        uses: alesangreat/QZX-Quick-Zap-Exchange@6a912448c7b2aa41c2a48923c355c422c02cd7a2
        with:
          profile: core
          success: result-contract-evidence/success.json
          failure: result-contract-evidence/failure.json
          report: result-contract-evidence/qzx-conformance.json

      - name: Preserve QZX conformance receipt
        if: always()
        uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7.0.1
        with:
          name: qzx-conformance-receipt
          path: result-contract-evidence/qzx-conformance.json
          if-no-files-found: error

      - name: Enforce QZX conformance gate
        if: steps.qzx-conformance.outcome == 'failure'
        shell: bash
        run: exit 1
```

`steps.qzx-conformance.outcome` remains `failure` for a nonconforming pair even
though `continue-on-error` lets the workflow reach the upload step. When the
validator reached a conformance verdict, the receipt also exposes
`conformant=false` and the same validation-material hashes used for PASS runs.
If the Action fails before a receipt can be written, `if-no-files-found: error`
keeps that missing evidence visible instead of silently pretending it was
preserved.

## 4. MCP 2025-06-18 and newer: use the contract as `outputSchema`

MCP 2025-06-18 already supports `outputSchema`, `structuredContent`, and
`isError`. QZX therefore supports three revision-specific profiles:
`mcp-2025-06-18`, `mcp-2025-11-25`, and `mcp-2026-07-28`. Choose the profile
matching the MCP revision your producer actually implements; you do not need to
upgrade an otherwise-compatible server just to try QZX Result Contract.

When the SDK permits it, the smallest canonical form is to declare the public
QZX schema as the tool's `outputSchema`:

```json
{
  "outputSchema": {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$ref": "https://qzx.yumbale.com/schemas/result-contract-v1.schema.json"
  }
}
```

QZX records that relationship as `canonical_ref`. It is convenient when the
producer intentionally follows compatible v1 clarifications published at the
canonical URL. For a long-lived integration whose accepted schema bytes should
change only with a reviewed repository change, vendor the exact canonical
schema and emit that JSON Schema object inline as `outputSchema`; keep its
canonical `$id` intact. A byte-identical copy is reported as `canonical_inline`,
and the conformance receipt records `contract_schema_sha256` so reviewers can
compare the exact QZX schema used by the validator. Update the vendored copy and
its expected digest deliberately rather than letting a remote alias change the
build implicitly.

If an SDK only accepts object-shaped schemas, keep the existing typed domain
schema and add required `success`/`message` plus an `error` or `error_code`
field with the QZX constraints. QZX records that portable form as
`structural_core`; it remains conformant when the submitted success/failure
results pass the complete canonical contract, but the receipt makes clear that
`outputSchema` alone is not a full canonical embedding. SDKs that support
`allOf` can instead compose the QZX `$ref` — or the vendored canonical schema
object for a byte-stable build — with their domain schema and receive the
stronger `canonical_allof` mode.

For a completed successful call:

- put the complete QZX object in `structuredContent`;
- set `structuredContent.success` to `true`;
- keep the effective MCP `isError` state `false`; the field may be omitted because MCP treats omission as `false`.

For a completed tool-execution failure:

- put the complete QZX failure object in `structuredContent`;
- set `structuredContent.success` to `false`;
- set MCP `isError` to `true`.

For MCP 2026-07-28, a completed result must also carry
`resultType: "complete"`. Do not add that requirement to 2025-06-18 or
2025-11-25 evidence. Keep MCP/JSON-RPC **protocol errors** as protocol errors;
do not manufacture a completed QZX result for an invalid request or other
protocol-level failure.

Validate both completed results and the tool definition in one receipt with the
profile matching the producer. For example:

```bash
python scripts/validate_result_contract_evidence.py \
  --profile mcp-2025-11-25 \
  --success result-contract-evidence/success.json \
  --failure result-contract-evidence/failure.json \
  --tool-definition result-contract-evidence/tool-definition.json \
  --report result-contract-evidence/qzx-conformance.json
```

In the Composite Action, use the same revision-specific `profile` and add:

```yaml
          tool-definition: result-contract-evidence/tool-definition.json
```

The repository includes copyable fixtures under
[`examples/result_contract/`](../examples/result_contract/). Use
`mcp-2025-success.json` / `mcp-2025-failure.json` for real 2025 wire examples
without `resultType`, `mcp-success.json` / `mcp-failure.json` for the 2026-07-28
`complete` shape, `mcp-tool-definition.json` for `canonical_ref`, and
`mcp-structural-tool-definition.json` for the SDK-portable `structural_core`
case. Contradictory `isError` and protocol-error fixtures remain available for
negative testing.

## 5. Publish the smallest reviewable evidence bundle

A first independent implementation does not need a white paper. A small public
directory is enough when it contains:

```text
result-contract-evidence/
  README.md
  tool-definition.json        # when MCP applies
  success.json
  failure.json
  qzx-conformance.json        # generated deterministic receipt
```

In `README.md`, state:

- implementation name and immutable version or revision;
- QZX Result Contract version (`v1`) and QZX validator/action commit SHA;
- runtime, operating system, transport, and MCP version when applicable;
- extensions, unsupported cases, lossy mappings, and known limitations;
- a correction or issue URL.

The generated receipt records the exact input file digests and validator
findings. Negative results are useful: a pilot that finds an ambiguity or
rejects the profile can be more valuable than an uncritical compatibility
claim.

## 6. Report independent evidence — or start before you are ready

If you are still experimenting, blocked on a mapping, or do not yet have public
evidence, open the short **Result Contract pilot or integration help** form:
<https://github.com/alesanGreat/QZX-Quick-Zap-Exchange/issues/new?template=result_contract_pilot.yml>.
A pilot-help issue is an invitation to collaborate, not an adoption claim.

Use the stricter **Result Contract adoption report** only when the evidence is
public and reviewable. QZX lists only evidence-backed implementations or pilots
in [`ADOPTERS.md`](../ADOPTERS.md).

QZX does **not** count itself, package downloads, website visits, private
conversations, expressions of interest, or unverifiable statements as external
adoption.

For the full semantics, transport profiles, evidence requirements, and pilot
template, continue with
[`result-contract-adoption.md`](result-contract-adoption.md).
