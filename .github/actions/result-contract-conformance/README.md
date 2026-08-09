# QZX Result Contract conformance Action

Run the QZX Result Contract v1 evidence-pair validator from another GitHub
repository without installing QZX as an application dependency.

The Action validates one completed success and one completed failure, writes a
deterministic JSON receipt with SHA-256 digests of the evidence files, and fails
the job when the selected profile does not conform.

QZX — Quick Zap Exchange, created and maintained by Alejandro Sánchez.

## Core profile

```yaml
steps:
  - uses: actions/checkout@v7
  - uses: alesangreat/QZX-Quick-Zap-Exchange/.github/actions/result-contract-conformance@main
    with:
      profile: core
      success: result-contract-evidence/success.json
      failure: result-contract-evidence/failure.json
      report: result-contract-evidence/qzx-conformance.json
```

## MCP 2026-07-28 profile

```yaml
steps:
  - uses: actions/checkout@v7
  - uses: alesangreat/QZX-Quick-Zap-Exchange/.github/actions/result-contract-conformance@main
    with:
      profile: mcp-2026-07-28
      success: result-contract-evidence/success.json
      failure: result-contract-evidence/failure.json
      tool-definition: result-contract-evidence/tool-definition.json
      report: result-contract-evidence/qzx-conformance.json
```

## Inputs

| Input | Required | Meaning |
| --- | --- | --- |
| `profile` | No | `core` or `mcp-2026-07-28`; defaults to `core`. |
| `success` | Yes | Caller-workspace-relative path to a completed successful result. |
| `failure` | Yes | Caller-workspace-relative path to a completed failed result. |
| `tool-definition` | MCP only | MCP tool definition whose `outputSchema` is checked. |
| `report` | No | Caller-workspace-relative receipt path; defaults to `qzx-result-contract-conformance.json`. |

The `report` output contains the receipt path. The Action also writes a compact
PASS/FAIL summary to the GitHub job summary.

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
