# Adopting QZX Result Contract v1

QZX Result Contract v1 is an open, additive JSON envelope for command, tool,
automation, MCP-server, and AI-agent results. An implementation can adopt the
contract without using QZX command names, Python, or the QZX runtime.

The normative core is documented in
[`result-contract-v1.md`](result-contract-v1.md) and published as JSON Schema at
<https://qzx.yumbale.com/schemas/result-contract-v1.schema.json>. QZX is the
reference implementation, not proof that the contract has become an industry
standard.

QZX — Quick Zap Exchange, created and maintained by Alejandro Sánchez.

## Adoption modes

### 1. Native producer

A tool emits one object containing at least:

```json
{
  "success": true,
  "message": "The operation completed."
}
```

Domain evidence remains additive. A producer may include `details`, `warnings`,
`meta`, or its own descriptive fields without asking QZX for permission.

### 2. Adapter

An adapter translates an existing result into the QZX envelope while
preserving the original domain data. This is useful when replacing an old API
is impractical or when several tools need a common outer contract.

The adapter must not convert an unknown outcome into success merely because no
exception was raised. It should preserve the source error and state any lossy
mapping explicitly.

### 3. Consumer only

A client may consume QZX-conforming results without producing them. It should
check the process or transport status, parse exactly one JSON document, inspect
`success`, and present `message` plus relevant domain evidence. It must not infer
success from a missing `error` field.

### 4. Pilot or interoperability study

An organization can compare its current result format with QZX Result Contract
v1 on a bounded set of real tasks. A useful pilot measures parsing failures,
extra tool calls, retries, latency, completion rate, and operator effort rather
than assuming that structured JSON is always shorter or better.

## Minimum conformance evidence

A credible adoption report includes:

1. implementation name, version, repository or reviewable source boundary;
2. the exact QZX Result Contract version and schema URL;
3. at least one successful and one failed result when the producer can fail;
4. exit-code or transport-status behavior;
5. the validation command and its complete sanitized result;
6. limitations, extensions, lossy mappings, and unsupported cases;
7. the operating systems, runtimes, or services actually exercised;
8. a contact or issue URL for corrections.

Passing the core schema does not certify security, authorization, isolation,
correct domain behavior, platform compatibility, or every extension field. A
report must keep those claims separate.

## Included conformance suite

The repository contains positive and negative fixtures under
[`examples/result_contract/`](../examples/result_contract/) and a
dependency-free runner:

```bash
python scripts/run_result_contract_conformance.py
python scripts/run_result_contract_conformance.py --json
```

The suite proves that an implementation agrees with the QZX core validator on
known examples. It is a baseline, not a substitute for testing the adopter's
real producer.

A single document can be checked with:

```bash
python scripts/validate_result_contract.py result.json
```

## Reporting an implementation

Use the GitHub issue form **Result Contract adoption report**. Public reports
may be linked from [`ADOPTERS.md`](../ADOPTERS.md) only when they provide
reviewable evidence and permission to identify the implementation or
organization.

QZX does not list private conversations, expressions of interest, package
downloads, website visits, or unverifiable claims as adoption. A report can be
removed or marked historical when its evidence disappears or no longer matches
the named version.

## Enterprise pilot template

A bounded pilot should define these items before work begins:

| Item | Required decision |
| --- | --- |
| Current problem | Which ambiguous, inconsistent, or hard-to-parse result is being addressed? |
| Task set | Which concrete commands, tools, or workflows are included and excluded? |
| Baseline | How does the current format behave on the same tasks? |
| Contract mapping | Which fields are core, additive, adapted, or intentionally omitted? |
| Environments | Which OS, runtime, architecture, agent, transport, and permissions are tested? |
| Safety boundary | What authorizes execution, and what remains outside the result contract? |
| Metrics | Completion, retries, parse failures, tool calls, latency, tokens, and human review effort as applicable. |
| Publication | Which methodology, fixtures, findings, and limitations may be made public? |
| Exit criteria | What result ends, extends, or rejects the pilot? |

A funded pilot purchases defined work and evidence. It does not purchase a
favorable compatibility result, control of the public contract, private user
telemetry, or automatic inclusion in the adopters register.

## Contribution paths

Useful contributions include:

- counterexamples that satisfy the schema but expose unclear semantics;
- examples from non-Python implementations;
- streaming, partial-result, retry, batch, and nested-tool use cases;
- failure taxonomies and remediation patterns;
- conformance runners in maintained ecosystems;
- security review of consumers that incorrectly trust structured output;
- real pilot reports, including negative results.

Material changes to the required core belong in a reviewed proposal and a new
contract version. Additive examples, clarifications, validators, and adoption
evidence may improve without changing the v1 required fields.
