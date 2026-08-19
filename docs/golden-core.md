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
| `getSystemInfo` | Environment context | Identifies OS, architecture, Python, user context, and optional resources. |
| `getDiskSpace` | Storage capacity | Reports raw and human-readable disk capacity before data-intensive work. |
| `getRamInfo` | Memory capacity | Reports memory capacity and pressure for workload decisions. |
| `listFiles` | Directory inventory | Provides wildcard and depth-controlled file inventory. |
| `findFiles` | File discovery | Adds explicit depth, size, date, exclusions, sorting, and truncation. |
| `findText` | Content search | Searches text with matching, context, filters, and limits. |
| `calculateFileHash` | Integrity observation | Produces reproducible cryptographic file identities. |
| `getGitStatus` | Repository state | Summarizes branch, remote, changes, and history without mutation. |
| `diagnoseProject` | Project diagnostics | Performs bounded static inspection without running project-owned workflows. |
| `checkUrlStatus` | Endpoint observation | Adds one bounded HTTP status, latency, and header observation. |

The cohort deliberately includes commands with different evidence challenges.
`checkUrlStatus` requires an authorized endpoint and `getGitStatus` requires a
representative native Git repository. The current readiness board records
controlled loopback HTTP and disposable Git-fixture captures for both commands;
those local results close the successful-capture dimension but do not become
cross-platform evidence or justify Beta promotion by themselves.

## Readiness dimensions

A Golden Core command is evaluated across independent dimensions:

- maintained behavioral tests;
- a current safety and external-effect review bound to its implementation
  digest;
- captured successful `--json` output;
- representative failure or boundary evidence where meaningful;
- a reviewed implementation-backed result contract;
- real platform evidence for the relevant operating systems and dependencies;
- a machine-verifiable release-quality attestation bound to an exact published
  release, verified artifacts, current implementation digests, successful CI,
  and zero known `release-blocker` issues;
- a machine-validated lifecycle review for any promotion beyond Alpha.

Passing one dimension never substitutes for another. Mocked unit tests do not
become platform evidence, a captured success does not prove every failure path,
and inclusion in Golden Core does not freeze an interface.

While QZX remains Alpha, an intentional breaking rename can temporarily make a
selected command development-only even though the previous published package
contains its predecessor name. The catalog must expose that availability
honestly instead of rejecting the whole cohort or pretending the new name is
already installable from PyPI. Such a command cannot satisfy release quality
until an exact release containing the current name and implementation is
published and attested.

### Failure evidence must be meaningful, not manufactured

Golden Core classifies the failure-or-boundary dimension explicitly. Ten
commands expose a useful caller-controlled failure boundary and therefore need a
captured failed result. Five commands (`version`, `listCommands`,
`getCurrentDirectory`, `getSystemInfo`, and `getRamInfo`) have no representative
caller-controlled domain failure in their ordinary interface; their failure
requirement is marked **not applicable** with a bilingual rationale in the
canonical registry.

Not-applicable is a resolved assessment, not a successful failure test. QZX does
not deliberately break an operating-system API, inject a fake `psutil` failure,
or reinterpret a valid empty result merely to make a dashboard count turn
green. If a meaningful public failure boundary is introduced later, the policy
must be updated and the new boundary captured.

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

## Platform evidence pipeline

The existing GitHub Actions matrix runs the Golden Core evidence capturer after
the normal tests on Windows, Linux, and macOS. Each runner executes all 15
commands through the real CLI with disposable file, project, Git, and loopback
HTTP fixtures, then uploads one sanitized JSON record. Every command record is
bound to QZX's canonical transitive implementation digest, not just to the
repository SHA. A separate job downloads those records and refuses to produce
an aggregate unless they share one source revision, one QZX version, valid
result hashes, the complete command set, one implementation digest per command,
and observed Windows, Linux, and macOS hosts. This makes code drift explicit
instead of allowing two different implementations to hide behind matching
release metadata.

The public tools are:

```bash
python scripts/capture_golden_core_platform_evidence.py \
  --output evidence.json \
  --environment-id <stable-id> \
  --environment-name "<display name>"

python scripts/merge_golden_core_platform_evidence.py \
  <evidence-file-or-directory> \
  --output summary.json
```

Raw records may include real operating-system, architecture, Python, resource,
and command-result facts. They replace private paths, usernames, hostnames, and
ephemeral loopback ports before hashing and upload. The JSON writers normalize
to UTF-8 with LF endings, and the merger derives its timestamp and stable source
names from the evidence itself, so identical records produce identical bytes
regardless of input order, download directory, or host line-ending convention.
The aggregate proves only the exact revision, command implementation digests,
environments, fixtures, arguments, and observed results; it is not a universal
compatibility guarantee or an automatic Beta promotion.

### Submit independent platform evidence

Run the capturer from a clean checkout at the exact full commit SHA you intend
to report, open the generated JSON, and review it manually before publishing.
The automatic replacements cover known checkout, home, user, hostname, fixture,
and ephemeral-port values; they are a defense in depth, not permission to upload
an unreviewed file. Never publish credentials, private remotes, internal
addresses, personal data, proprietary content, or a security vulnerability.

Use the
[Golden Core platform evidence form](https://github.com/alesanGreat/QZX-Quick-Zap-Exchange/issues/new?template=golden_core_evidence.yml)
to attach the sanitized record or submit a selected-command failure,
counterexample, or portability limitation. The form asks for the immutable QZX
revision, exact environment, command and exit status, repetitions, limitations,
and public credit preference so a reviewer can distinguish independent evidence
from QZX's own CI matrix. Negative findings are welcome and do not need to make
the project look successful to be useful.

## Release-quality attestation

Release quality is a separate, fail-closed evidence layer. The canonical Golden
Core registry points to one public JSON attestation for an exact published
release. The verifier requires the immutable tag, wheel and source distribution,
PyPI hashes, GitHub Release asset hashes, `twine check`, a successful CI matrix,
digest-bound platform evidence, the Result Contract gate, and zero open issues
carrying the `release-blocker` label.

The current attestation is stored under `docs/release-quality/` and can be
validated without trusting the website:

```bash
python scripts/verify_golden_core_release_quality.py --verify-git --json
```

Open issues without the `release-blocker` label remain visible as non-blocking
work. That distinction is intentional: an adoption request or a request for
additional independent evidence is not silently converted into a known defect.
Conversely, a real release-blocking defect must receive the explicit label and
will make the attestation fail.

The attestation is bound per command to the canonical implementation digest. A
later development version may reuse the release-quality evidence only while the
attested command implementation is byte-semantically identical under QZX's
portable fingerprint. Changing one command invalidates the release-quality gate
for that command without erasing valid evidence for unrelated commands.

Release quality still does **not** promote maturity. Beta requires a separate
lifecycle review that justifies the stronger interface and behavior promise.

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
