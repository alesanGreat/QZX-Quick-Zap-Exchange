# QZX Result Contract conformance Action

Run the QZX Result Contract v1 evidence-pair validator from another GitHub
repository without installing QZX as an application dependency.

The Action validates one completed success and one completed failure, writes a
deterministic JSON receipt with SHA-256 digests of the evidence files, and fails
the job when the selected profile does not conform. Every receipt identifies the
public QZX Result Contract Conformance Receipt v1 schema:
`https://qzx.yumbale.com/schemas/result-contract-conformance-receipt-v1.schema.json`.
That schema lets a reviewer validate the receipt structure without running QZX;
a schema-valid receipt can still report failed conformance.

QZX — Quick Zap Exchange, created and maintained by Alejandro Sánchez.

## Core profile

```yaml
steps:
  - uses: actions/checkout@v7
  - id: qzx-conformance
    uses: alesangreat/QZX-Quick-Zap-Exchange/.github/actions/result-contract-conformance@main
    with:
      profile: core
      success: result-contract-evidence/success.json
      failure: result-contract-evidence/failure.json
      report: result-contract-evidence/qzx-conformance.json
```

## MCP structured-output profiles

Use the profile matching the MCP revision actually implemented by the producer:
`mcp-2025-06-18`, `mcp-2025-11-25`, or `mcp-2026-07-28`. The two 2025 profiles
validate completed tool results without requiring `resultType`; MCP 2026-07-28
requires `resultType: "complete"`. MCP receipts also expose an
`output_schema_mode`: canonical `$ref`/inline/`allOf` relationships are reported
separately from the weaker `structural_core` mode used by object-schema-only
SDKs, where the submitted runtime evidence is validated separately against the
complete QZX Result Contract.

```yaml
steps:
  - uses: actions/checkout@v7
  - id: qzx-conformance
    uses: alesangreat/QZX-Quick-Zap-Exchange/.github/actions/result-contract-conformance@main
    with:
      profile: mcp-2025-11-25
      success: result-contract-evidence/success.json
      failure: result-contract-evidence/failure.json
      tool-definition: result-contract-evidence/tool-definition.json
      report: result-contract-evidence/qzx-conformance.json
```

## Inputs

| Input | Required | Meaning |
| --- | --- | --- |
| `profile` | No | `core`, `mcp-2025-06-18`, `mcp-2025-11-25`, or `mcp-2026-07-28`; defaults to `core`. |
| `success` | Yes | Caller-workspace-relative path to a completed successful result. |
| `failure` | Yes | Caller-workspace-relative path to a completed failed result. |
| `tool-definition` | MCP only | MCP tool definition whose `outputSchema` is checked. |
| `report` | No | Caller-workspace-relative receipt path; defaults to `qzx-result-contract-conformance.json`. |

## Outputs

| Output | Meaning |
| --- | --- |
| `report` | Caller-workspace-relative path to the generated receipt. |
| `conformant` | `true` only when the selected profile conforms; otherwise `false`. |
| `profile` | Profile actually evaluated by the validator. |
| `receipt_schema` | Canonical schema URL declared by the generated receipt. |
| `output_schema_mode` | MCP schema evidence mode (`canonical_ref`, `canonical_inline`, `canonical_allof`, `structural_core`), or `not_applicable`. |

These scalar outputs make the Action composable from later workflow steps while
the JSON receipt remains the durable evidence artifact. The Action also writes
a compact PASS/FAIL summary with links to the specification and its creator to
the GitHub job summary.

## Evidence and security boundary

For a quick experiment, `@main` is convenient. Before publishing durable
adoption evidence, replace it with the full QZX commit SHA that was actually
used.

Evidence and report paths are restricted to `GITHUB_WORKSPACE`; line breaks in
Action path inputs are rejected. The validator does not execute the evidence
files. It parses JSON and evaluates QZX Result Contract/profile invariants.

Passing this Action does not certify security, authorization, domain
correctness, platform compatibility, or endorsement by QZX. It certifies only
the named Result Contract/profile checks at the pinned QZX revision.
