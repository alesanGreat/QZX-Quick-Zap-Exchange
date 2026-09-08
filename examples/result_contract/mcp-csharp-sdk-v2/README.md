# Official MCP C# SDK 2.2.0 interoperability evidence

This QZX-maintained reference executes one successful and one failed tool call
through the [official MCP C# SDK](https://github.com/modelcontextprotocol/csharp-sdk)
stable release `2.2.0` on .NET 10 LTS. The official client and server negotiate
MCP `2026-07-28` and communicate through the SDK's stream transports over paired
in-memory pipes, exercising its newline-delimited JSON-RPC framing. The
client-observed SDK models are serialized with `System.Text.Json` and validated
against QZX Result Contract v1.

This example is **not independent adoption**, endorsement, certification, or
evidence from the MCP maintainers. It is a reproducible compatibility test
created and maintained by the QZX project.

## What the example proves

- the official C# client and server actually negotiate MCP `2026-07-28`;
- the server exposes the canonical QZX schema unchanged as the tool's
  `outputSchema`, producing `output_schema_mode: canonical_inline`;
- the official client observes `resultType: "complete"`, structured content,
  backwards-compatible text, a successful result, and an `isError: true`
  failed result that pass the public QZX evidence validator;
- `ModelContextProtocol.Core` is pinned exactly to `2.2.0`, and
  `packages.lock.json` authenticates the resolved NuGet graph with content
  hashes;
- `global.json` selects .NET SDK `10.0.400`, while the project targets the
  supported `net10.0` LTS framework.

The serializer pins LF newlines, so `tool-definition.json`, `success.json`, and
`failure.json` have byte-identical SHA-256 digests on Windows and Linux for the
same source revision. `evidence-metadata.json` remains environment-specific by
design because it records the actual runtime and operating system. Generation
fails closed if any of the three contract evidence digests changes, and the
metadata publishes the observed digest map for review.

The in-process stream transport exercises JSON-RPC serialization but does not
exercise HTTP or SSE, and this example does not retain raw frames. Its evidence
metadata records those boundaries explicitly. The neighboring
[TypeScript SDK example](../mcp-typescript-sdk-v2/README.md) complements this
path by retaining actual Streamable HTTP response bodies.

## Reproduce on Windows PowerShell

Install .NET SDK 10.0.400 and standard CPython 3.13, then run from the public
repository root. All NuGet packages, build outputs, and generated evidence stay
outside the checkout.

```powershell
Push-Location examples/result_contract/mcp-csharp-sdk-v2
$env:NUGET_PACKAGES = Join-Path $env:LOCALAPPDATA "ValisIdealis\QZX\dependencies\nuget-packages"
$artifacts = Join-Path $env:LOCALAPPDATA "ValisIdealis\QZX\cache\dotnet\mcp-csharp-sdk-v2.2.0"
$evidence = Join-Path $env:TEMP "ValisIdealis\QZX\runs\mcp-csharp-sdk-v2.2.0-evidence"
$schema = Resolve-Path "../../../src/qzx/resources/schemas/result-contract-v1.schema.json"
dotnet restore --locked-mode --artifacts-path "$artifacts"
dotnet build --no-restore --configuration Release --artifacts-path "$artifacts"
dotnet run --no-build --configuration Release --artifacts-path "$artifacts" -- "$schema" "$evidence"
python -B ../../../scripts/validate_result_contract_evidence.py `
  --profile mcp-2026-07-28 `
  --success "$evidence/success.json" `
  --failure "$evidence/failure.json" `
  --tool-definition "$evidence/tool-definition.json" `
  --report "$evidence/qzx-conformance.json" `
  --json
Pop-Location
```

## Reproduce on Linux or macOS

```bash
cd examples/result_contract/mcp-csharp-sdk-v2
export NUGET_PACKAGES="${XDG_CACHE_HOME:-$HOME/.cache}/ValisIdealis/QZX/dependencies/nuget-packages"
artifacts="${XDG_CACHE_HOME:-$HOME/.cache}/ValisIdealis/QZX/cache/dotnet/mcp-csharp-sdk-v2.2.0"
evidence="${TMPDIR:-/tmp}/ValisIdealis/QZX/runs/mcp-csharp-sdk-v2.2.0-evidence"
schema="../../../src/qzx/resources/schemas/result-contract-v1.schema.json"
dotnet restore --locked-mode --artifacts-path "$artifacts"
dotnet build --no-restore --configuration Release --artifacts-path "$artifacts"
dotnet run --no-build --configuration Release --artifacts-path "$artifacts" -- "$schema" "$evidence"
python3.13 -B ../../../scripts/validate_result_contract_evidence.py \
  --profile mcp-2026-07-28 \
  --success "$evidence/success.json" \
  --failure "$evidence/failure.json" \
  --tool-definition "$evidence/tool-definition.json" \
  --report "$evidence/qzx-conformance.json" \
  --json
```

A passing receipt reports zero warnings and `canonical_inline` for both cases.
CI uses the same locked restore and keeps .NET artifacts under the runner's
temporary directory; only the reviewable evidence bundle is uploaded.

QZX — Quick Zap Exchange, created and maintained by Alejandro Sánchez.
