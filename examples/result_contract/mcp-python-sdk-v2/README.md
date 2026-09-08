# Official MCP Python SDK v2 interoperability evidence

This QZX-maintained reference executes one successful and one failed tool call
through the official MCP Python SDK 2.0.0. The official high-level `Client`
connects to the official low-level `Server` with its MCP 2026-07-28 in-process
direct dispatcher. The resulting SDK models are serialized with their MCP wire
aliases and validated against QZX Result Contract v1.

This example is **not independent adoption**, endorsement, certification, or
evidence from the MCP maintainers. It is a reproducible compatibility test
created and maintained by the QZX project.

## What the example proves

- the official Python client adopts exactly MCP `2026-07-28`;
- the official server exposes the canonical QZX schema unchanged as the tool's
  `outputSchema`, producing `output_schema_mode: canonical_inline`;
- a real official client call returns `structuredContent`, the backwards-
  compatible text block, explicit `isError`, and `resultType: "complete"`;
- both the success and failure results pass the public QZX evidence validator;
- the exact dependency graph is pinned with hashes in `requirements.txt`.

The in-process direct dispatcher intentionally does not exercise HTTP, SSE, or
JSON-RPC framing. Its evidence metadata records
`jsonrpc_framing_exercised: false`. The neighboring
[TypeScript SDK example](../mcp-typescript-sdk-v2/README.md) complements this
test by capturing actual Streamable HTTP response bodies.

## Reproduce on Windows PowerShell

Run these commands from the public repository root with the standard CPython
3.13 build:

```powershell
$venv = Join-Path $env:LOCALAPPDATA "ValisIdealis\QZX\dependencies\mcp-python-sdk-v2"
$evidence = Join-Path $env:TEMP "ValisIdealis\QZX\runs\mcp-python-sdk-v2-evidence"
python -m venv $venv
& "$venv\Scripts\python.exe" -m pip install --require-hashes `
  -r examples/result_contract/mcp-python-sdk-v2/requirements.txt
& "$venv\Scripts\python.exe" `
  examples/result_contract/mcp-python-sdk-v2/generate_evidence.py $evidence
& "$venv\Scripts\python.exe" scripts/validate_result_contract_evidence.py `
  --profile mcp-2026-07-28 `
  --success "$evidence/success.json" `
  --failure "$evidence/failure.json" `
  --tool-definition "$evidence/tool-definition.json" `
  --report "$evidence/qzx-conformance.json" `
  --json
```

## Reproduce on Linux or macOS

```bash
venv="${XDG_CACHE_HOME:-$HOME/.cache}/ValisIdealis/QZX/dependencies/mcp-python-sdk-v2"
evidence="${TMPDIR:-/tmp}/ValisIdealis/QZX/runs/mcp-python-sdk-v2-evidence"
python3.13 -m venv "$venv"
"$venv/bin/python" -m pip install --require-hashes \
  -r examples/result_contract/mcp-python-sdk-v2/requirements.txt
"$venv/bin/python" \
  examples/result_contract/mcp-python-sdk-v2/generate_evidence.py "$evidence"
"$venv/bin/python" scripts/validate_result_contract_evidence.py \
  --profile mcp-2026-07-28 \
  --success "$evidence/success.json" \
  --failure "$evidence/failure.json" \
  --tool-definition "$evidence/tool-definition.json" \
  --report "$evidence/qzx-conformance.json" \
  --json
```

A passing receipt reports zero violations and `canonical_inline` for both
cases. Evidence stays outside the checkout in these local examples; CI uses an
ephemeral caller workspace because the Composite Action deliberately restricts
all evidence and report paths to `GITHUB_WORKSPACE`.

QZX — Quick Zap Exchange, created and maintained by Alejandro Sánchez.
