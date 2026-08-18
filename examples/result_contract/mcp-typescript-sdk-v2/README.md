# Official MCP TypeScript SDK v2 interoperability evidence

This example runs one success and one tool-execution failure through the
official MCP TypeScript SDK 2.0.0, captures the actual MCP 2026-07-28 wire
results, and produces inputs for the QZX Result Contract evidence validator.

It is maintained QZX reference evidence, **not independent adoption**, an MCP
SDK certification, or proof of production transport, authorization, or domain
behavior.

QZX — Quick Zap Exchange, created and maintained by Alejandro Sánchez.

## What the example proves

- the official `@modelcontextprotocol/server` and client packages can carry a
  complete QZX Result Contract v1 object in `structuredContent`;
- `fromJsonSchema` advertises the exact canonical schema as `outputSchema`, so
  QZX reports `canonical_inline` rather than the weaker `structural_core` mode;
- successful and failed completed calls keep `isError` consistent with
  `!structuredContent.success`;
- the serialized compatibility text matches the structured object;
- the captured wire results include `resultType: "complete"` as required by
  MCP 2026-07-28.

The example uses a synthetic lookup tool and an in-process HTTP `fetch` bridge.
No socket, credentials, external service, or user data are involved.

## Why it does not use the in-memory transport

The official SDK 2.0.0 keeps 2025 behavior by default. Its own 2026 migration
guide states that `InMemoryTransport.createLinkedPair()` exercises 2025-era
instances only; modern in-process tests should drive `createMcpHandler` through
`StreamableHTTPClientTransport`. The client must also opt in with an explicit
2026-07-28 version pin.

The SDK intentionally removes the wire-only `resultType` discriminator before
returning a public `CallToolResult`. Because QZX's 2026 profile validates the
real wire contract, this example captures the JSON-RPC response at the HTTP
transport boundary instead of manufacturing `resultType` after the call.

See the official, version-pinned
[`Supporting protocol revision 2026-07-28`](https://github.com/modelcontextprotocol/typescript-sdk/blob/v2.0.0/docs/migration/support-2026-07-28.md)
guide for those SDK behaviors.

## Reproduce locally

Requirements: Node.js 20 or newer, pnpm 10.29.2, and the CPython 3.13 runtime
used by QZX. From the repository root in PowerShell:

```powershell
$evidence = Join-Path $env:TEMP "qzx-mcp-typescript-sdk-v2-evidence"
Push-Location examples/result_contract/mcp-typescript-sdk-v2
corepack enable
corepack prepare pnpm@10.29.2 --activate
pnpm install --frozen-lockfile --ignore-scripts
pnpm run evidence -- $evidence
Pop-Location

python scripts/validate_result_contract_evidence.py `
  --profile mcp-2026-07-28 `
  --success "$evidence/success.json" `
  --failure "$evidence/failure.json" `
  --tool-definition "$evidence/tool-definition.json" `
  --report "$evidence/qzx-conformance.json"
```

The generated tool definition, success result, failure result, and
`evidence-metadata.json` live in the operating-system temporary directory,
outside the source checkout. The metadata records the exact SDK packages,
runtime, transport, protocol, and the explicit `independent_adoption: false`
claim boundary. A conforming receipt reports
`output_schema_mode: canonical_inline` for both cases.

CI runs the same locked dependency graph on Node.js 22, validates the pair
through QZX's public Composite Action, and publishes the evidence bundle as a
short-lived workflow artifact for review. That artifact also includes this
README so the limitations travel with the generated result files and receipt.
