# QZX Golden Core

QZX Golden Core is a **candidate development focus cohort** maintained by
Alejandro Sánchez. It concentrates contract review, behavioral testing, real
execution evidence, and compatibility work on 15 high-frequency read-only
commands before QZX makes stronger maturity promises.

It is not a paid edition, a second runtime, a certification, an industry
standard, a compatibility guarantee, or evidence of external adoption. Every
selected command remains part of the ordinary open-source QZX package and keeps
its own lifecycle stage. At the initial selection on 2026-08-08, all 15
commands are still Alpha.

The canonical machine-readable registry is
[`src/qzx/resources/golden-core.json`](../src/qzx/resources/golden-core.json).
It ships with QZX and is checked against the packaged command index, lifecycle
registry, and real command loader by
[`scripts/verify_golden_core.py`](../scripts/verify_golden_core.py).

## Why a focused cohort exists

QZX has a broad executable catalog. Breadth is useful, but a large command count
is not a substitute for deep evidence. A smaller cohort makes progress visible:
which public contracts have tests, captured success and failure output,
reviewed safety classifications, relevant platform evidence, and a documented
reason for promotion.

The Golden Core therefore has two goals:

1. give users and reviewers a compact set of capabilities on which to focus;
2. create a reproducible path from Alpha to Beta without pretending that time,
   popularity, or a marketing label proves maturity.

## Selected commands

| Command | Role | Why it is included |
| --- | --- | --- |
| `version` | Identity | Binds later observations to the exact installed QZX version. |
| `listCommands` | Capability discovery | Lets the installed runtime describe what it can execute. |
| `help` | Interface discovery | Exposes parameters, examples, safety notes, and maturity before use. |
| `getCurrentDateTime` | Temporal context | Returns timezone-aware date and timestamp context portably. |
| `getCurrentDirectory` | Workspace context | Reports the current path and bounded directory context. |
| `systemInfo` | Environment context | Identifies OS, architecture, Python, user context, and optional resources. |
| `getDiskSpace` | Storage capacity | Reports raw and human-readable disk capacity before data-intensive work. |
| `getRamInfo` | Memory capacity | Reports memory capacity and pressure for workload decisions. |
| `listFiles` | Directory inventory | Provides wildcard and depth-controlled file inventory. |
| `findFiles` | File discovery | Adds explicit depth, size, date, exclusions, sorting, and truncation. |
| `findText` | Content search | Searches text with matching, context, filters, and limits. |
| `getFileHash` | Integrity observation | Produces reproducible cryptographic file identities. |
| `getGitStatus` | Repository state | Summarizes branch, remote, changes, and history without mutation. |
| `projectDoctor` | Project diagnostics | Performs bounded static inspection without running project-owned workflows. |
| `checkUrlStatus` | Endpoint observation | Adds one bounded HTTP status, latency, and header observation. |

The cohort deliberately includes commands with different evidence challenges.
For example, `checkUrlStatus` needs a controlled external endpoint, and
`getGitStatus` needs representative native Git execution. These gaps are
visible work, not reasons to fabricate a passing score.

## Readiness dimensions

A Golden Core command is evaluated across independent dimensions:

- maintained behavioral tests;
- a current safety and external-effect review bound to its implementation
  digest;
- captured successful `--json` output;
- representative failure or boundary evidence where meaningful;
- a reviewed implementation-backed result contract;
- real platform evidence for the relevant operating systems and dependencies;
- no known release-blocking defect in the documented scope;
- a machine-validated lifecycle review for any promotion beyond Alpha.

Passing one dimension never substitutes for another. Mocked unit tests do not
become platform evidence, a captured success does not prove every failure path,
and inclusion in Golden Core does not freeze an interface.

## Verification

From a source checkout:

```bash
python scripts/verify_golden_core.py
```

A documentation or release pipeline can additionally validate reviewed safety
and package availability against its generated command catalog:

```bash
python scripts/verify_golden_core.py \
  --catalog <path-to-command-catalog.json> \
  --json
```

The verifier fails when a selected name disappears, stops being publicly
executable, requires QZX high-risk approval, declares a mutation backup target,
or conflicts with the reviewed catalog supplied by the workspace.

## Promotion and change policy

The target is Beta, not an automatic promotion. A command advances only after
its evidence justifies the stronger promise and its lifecycle entry contains
the required review. A command may be removed from the cohort if its
responsibility becomes redundant, its design needs substantial revision, or a
better-focused command replaces it during Alpha.

Changes to the cohort must update the canonical registry, this explanation,
tests, generated readiness surfaces, and any public announcement that names the
selected commands. Immutable QZX releases preserve the cohort and lifecycle
state they shipped.

## How organizations can help

Useful independent contributions include:

- sanitized output from real Windows, Linux, macOS, BSD, illumos, or Solaris
  environments;
- controlled compatibility laboratories and hardware access;
- contract and security review;
- reproducible failures and counterexamples;
- implementations that consume QZX Result Contract v1;
- bounded pilots with measurable tasks and publishable methodology.

Financial support can fund this work without purchasing a favorable result,
private control of the roadmap, or a false compatibility claim. See the
[QZX Result Contract adoption guide](result-contract-adoption.md) and the
[project support page](https://qzx.yumbale.com/en/donate).

QZX — Quick Zap Exchange, created and maintained by Alejandro Sánchez.
