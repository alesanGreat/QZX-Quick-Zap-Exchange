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
it does not require throwing useful evidence away.

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

## 3. MCP 2026-07-28: use the contract as `outputSchema`

For an MCP tool, declare the QZX schema as the tool's `outputSchema`:

```json
{
  "outputSchema": {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$ref": "https://qzx.yumbale.com/schemas/result-contract-v1.schema.json"
  }
}
```

For a completed successful call:

- put the complete QZX object in `structuredContent`;
- set `structuredContent.success` to `true`;
- set MCP `isError` to `false`.

For a completed tool-execution failure:

- put the complete QZX failure object in `structuredContent`;
- set `structuredContent.success` to `false`;
- set MCP `isError` to `true`.

Keep MCP/JSON-RPC **protocol errors** as protocol errors. Do not manufacture a
completed QZX result for an invalid request or other protocol-level failure.

Validate both the tool definition and completed result with:

```bash
python scripts/validate_mcp_result_contract.py path/to/mcp-result.json \
  --tool-definition path/to/mcp-tool-definition.json --json
```

The repository includes copyable fixtures under
[`examples/result_contract/`](../examples/result_contract/), including a tool
definition, completed success, completed failure, contradictory `isError`, and
protocol-error examples.

## 4. Publish the smallest reviewable evidence bundle

A first independent implementation does not need a white paper. A small public
directory is enough when it contains:

```text
result-contract-evidence/
  README.md
  tool-definition.json        # when MCP applies
  success.json
  failure.json                # when the producer can fail
  validation.txt              # command, exit status, sanitized output
```

In `README.md`, state:

- implementation name and immutable version or revision;
- QZX Result Contract version (`v1`);
- runtime, operating system, transport, and MCP version when applicable;
- extensions, unsupported cases, lossy mappings, and known limitations;
- a correction or issue URL.

Negative results are useful. A pilot that finds an ambiguity or rejects the
profile can be more valuable than an uncritical compatibility claim.

## 5. Report independent evidence

Use the GitHub issue form **Result Contract adoption report** when the evidence
is public and reviewable. QZX lists only evidence-backed implementations or
pilots in [`ADOPTERS.md`](../ADOPTERS.md).

QZX does **not** count itself, package downloads, website visits, private
conversations, expressions of interest, or unverifiable statements as external
adoption.

For the full semantics, transport profiles, evidence requirements, and pilot
template, continue with
[`result-contract-adoption.md`](result-contract-adoption.md).
