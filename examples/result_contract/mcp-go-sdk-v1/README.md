# Official MCP Go SDK v1.6.1 interoperability evidence

This QZX-maintained reference executes one successful and one failed tool call
through the [official MCP Go SDK](https://github.com/modelcontextprotocol/go-sdk)
stable release `v1.6.1`. The official client and server negotiate MCP
`2025-11-25` and communicate through the SDK's paired in-memory transport,
which exercises newline-delimited JSON-RPC framing. The resulting official SDK
models are serialized with Go's `encoding/json` and validated against QZX
Result Contract v1.

This example is **not independent adoption**, endorsement, certification, or
evidence from the MCP maintainers. It is a reproducible compatibility test
created and maintained by the QZX project.

## What the example proves

- the official Go client and server actually negotiate MCP `2025-11-25`;
- the server exposes the canonical QZX schema unchanged as the tool's
  `outputSchema`, producing `output_schema_mode: canonical_inline`;
- the SDK's typed `AddTool` path validates each output and fills both
  `structuredContent` and the backwards-compatible text block;
- the official client observes a successful result and an `isError: true`
  failed result that both pass the public QZX evidence validator;
- the Go module graph is pinned by `go.mod` and authenticated by `go.sum`.

Go's official SDK model intentionally omits `isError: false` from the serialized
success result because that field uses `omitempty`; MCP defines an absent value
as false, and the QZX receipt records both the explicit and effective states.

The in-process transport exercises JSON-RPC serialization but does not exercise
HTTP or SSE, and this example does not retain raw frames. Its evidence metadata
records `jsonrpc_framing_exercised: true` and
`wire_capture_retained: false`. The neighboring
[TypeScript SDK example](../mcp-typescript-sdk-v2/README.md) complements this
boundary by retaining actual Streamable HTTP response bodies for MCP
2026-07-28.

## Reproduce on Windows PowerShell

Run these commands from the public repository root with Go 1.25.x and standard
CPython 3.13:

```powershell
$env:GOMODCACHE = Join-Path $env:LOCALAPPDATA "ValisIdealis\QZX\dependencies\go-mod-cache"
$env:GOCACHE = Join-Path $env:LOCALAPPDATA "ValisIdealis\QZX\cache\go-build"
$evidence = Join-Path $env:TEMP "ValisIdealis\QZX\runs\mcp-go-sdk-v1.6.1-evidence"
go -C examples/result_contract/mcp-go-sdk-v1 run -mod=readonly . $evidence
go -C examples/result_contract/mcp-go-sdk-v1 mod verify
python -B scripts/validate_result_contract_evidence.py `
  --profile mcp-2025-11-25 `
  --success "$evidence/success.json" `
  --failure "$evidence/failure.json" `
  --tool-definition "$evidence/tool-definition.json" `
  --report "$evidence/qzx-conformance.json" `
  --json
```

## Reproduce on Linux or macOS

```bash
export GOMODCACHE="${XDG_CACHE_HOME:-$HOME/.cache}/ValisIdealis/QZX/dependencies/go-mod-cache"
export GOCACHE="${XDG_CACHE_HOME:-$HOME/.cache}/ValisIdealis/QZX/cache/go-build"
evidence="${TMPDIR:-/tmp}/ValisIdealis/QZX/runs/mcp-go-sdk-v1.6.1-evidence"
go -C examples/result_contract/mcp-go-sdk-v1 run -mod=readonly . "$evidence"
go -C examples/result_contract/mcp-go-sdk-v1 mod verify
python3.13 -B scripts/validate_result_contract_evidence.py \
  --profile mcp-2025-11-25 \
  --success "$evidence/success.json" \
  --failure "$evidence/failure.json" \
  --tool-definition "$evidence/tool-definition.json" \
  --report "$evidence/qzx-conformance.json" \
  --json
```

A passing receipt reports zero warnings and `canonical_inline` for both cases.
Evidence and Go caches stay outside the checkout in these local examples; CI
uses an ephemeral caller workspace for evidence because the Composite Action
restricts all inputs and reports to `GITHUB_WORKSPACE`.

QZX — Quick Zap Exchange, created and maintained by Alejandro Sánchez.
