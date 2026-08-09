# QZX Result Contract adopters

This register lists independently reviewable implementations or pilots of
**QZX Result Contract v1**. It does not count QZX itself, package downloads,
website traffic, private conversations, expressions of interest, or
unverifiable claims as external adoption.

## Current register

No independent adopters are listed yet.

QZX is the reference implementation. That proves the contract can be used by
QZX; it does not prove independent interoperability or industry adoption.

### First independent implementation wanted

The immediate adoption target is one small, public, independently reviewable
implementation or pilot. An MCP 2026-07-28 producer is especially useful
because the repository now includes success/failure fixtures and a dependency-
free profile validator for `outputSchema`, `structuredContent`, `isError`, and
QZX Result Contract consistency.

A useful first pilot does not need to replace an existing result format or
implement the QZX command vocabulary. It may wrap one real tool, document what
maps cleanly and what does not, and publish both successful and failed calls.
Negative findings are welcome; evidence matters more than a favorable outcome.

The shortest path is the
[`5-minute adoption quickstart`](docs/result-contract-quickstart.md), which
shows the minimal core, the reusable GitHub Action, and the MCP evidence bundle
before the full reporting requirements below.

For the included MCP fixtures, validate the complete success/failure pair and
produce the same deterministic receipt expected from independent evidence:

```bash
python scripts/validate_result_contract_evidence.py \
  --profile mcp-2026-07-28 \
  --success examples/result_contract/mcp-success.json \
  --failure examples/result_contract/mcp-failure.json \
  --tool-definition examples/result_contract/mcp-tool-definition.json \
  --report qzx-conformance.json
```

External GitHub repositories can run the same check through
[`.github/actions/result-contract-conformance`](.github/actions/result-contract-conformance/action.yml).
For durable evidence, pin the QZX Action to a full commit SHA rather than a
floating branch before publishing the result.

Independent work can be submitted directly. If the implementation is not ready
for the listing requirements below, use the short
[Result Contract pilot or integration help form](https://github.com/alesanGreat/QZX-Quick-Zap-Exchange/issues/new?template=result_contract_pilot.yml)
to ask a mapping question, share a sanitized current result shape, or start a
one-tool experiment without claiming adoption. An organization may also fund a
bounded interoperability pilot, but payment never guarantees conformance,
listing, favorable findings, or control of the public contract.

## Listing requirements

A public entry requires:

- permission to identify the implementation or organization;
- the implementation name and version or immutable revision;
- the exact QZX Result Contract version used;
- a public repository, report, or other reviewable source boundary;
- at least one conforming success result and one conforming failure result when
  the producer can fail;
- the validation command and sanitized result;
- the tested environments and known limitations;
- a correction contact or issue URL.

Passing the core validator does not certify security, authorization, domain
correctness, compatibility, or every extension field. Entries must keep those
claims separate.

## Submit evidence

Use the GitHub issue form **Result Contract adoption report**. The review may:

- accept the evidence and add a current entry;
- request reproducible details;
- list the work as an experiment rather than an adoption;
- reject claims that cannot be independently reviewed;
- mark an older entry historical when its referenced evidence disappears or no
  longer matches the named version.

The integration and pilot guidance is in
[`docs/result-contract-adoption.md`](docs/result-contract-adoption.md).

QZX — Quick Zap Exchange, created and maintained by Alejandro Sánchez.
