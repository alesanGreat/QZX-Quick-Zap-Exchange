# QZX — Quick Zap Exchange

QZX — Quick Zap Exchange, created and maintained by Alejandro Sánchez.

[About Alejandro Sánchez](https://qzx.yumbale.com/en/alejandro-sanchez) ·
[Contact QZX](mailto:qzx@yumbale.com) ·
[Support the project](https://qzx.yumbale.com/en/donate)

QZX is an open-source Python CLI that gives AI agents, automation, and people
one documented command vocabulary for supported operations on Windows, Linux,
and macOS.

QZX is completely free to use. There are no paid plans or paid features.
Donations are welcome because they support ongoing development, but they are
optional and never unlock features or change the product experience.

[Website](https://qzx.yumbale.com/en/) ·
[Command documentation](https://qzx.yumbale.com/en/commands) ·
[QZX Golden Core](https://qzx.yumbale.com/en/golden-core) ·
[QZX Result Contract v1](https://qzx.yumbale.com/en/result-contract) ·
[Recorded output](https://qzx.yumbale.com/en/qzx-in-action) ·
[Compatibility](https://qzx.yumbale.com/en/compatibility) ·
[Security and telemetry](https://qzx.yumbale.com/en/security) ·
[Documentación en español](https://qzx.yumbale.com/es/)

QZX is a local command interface, not a shell replacement, remote execution
service, or security sandbox. It reduces platform-specific branches only for
operations present in the installed command catalog.

## Install the published package

```bash
python -m pip install --upgrade qzx
qzx listCommands
qzx help findFiles
qzx getCurrentDateTime
qzx getCurrentDateTime --output-format iso --json
```

This source release is QZX `0.2.2.0.7a6` and requires Python `>=3.13`.
A normal `python -m pip install qzx` selects the latest final release; add
`--pre` to opt into the newest pre-release. PyPI is authoritative for which
version those commands currently select.

QZX supports the standard CPython 3.13.x build. Other Python versions or
implementations may work, but experimental free-threaded CPython builds, PyPy,
and other implementations are not certified.

| Source | Version | Python | Command surface |
|---|---:|---:|---|
| Source release described here | `0.2.2.0.7a6` | `>=3.13`; standard CPython 3.13.x is certified | 87 canonical commands in the generated command index |

PyPI is authoritative for what `pip install qzx` installs. The installed
runtime is authoritative for its own command list.

## Output contract

Every public command returns an object with at least:

- `success`: an explicit boolean outcome;
- `message`: a descriptive human-readable summary;
- command-specific evidence such as paths, counts, units, versions,
  diagnostics, causes, or remediation when available.

This transport-independent core is published as the open
[QZX Result Contract v1](docs/result-contract-v1.md), with a downloadable
[JSON Schema](https://qzx.yumbale.com/schemas/result-contract-v1.schema.json).
Other tools may implement the result envelope without adopting the QZX command
vocabulary or runtime. Start with the
[5-minute adoption quickstart](docs/result-contract-quickstart.md); the full
[adoption guide](docs/result-contract-adoption.md) includes revision-specific
interoperability profiles for MCP 2025-06-18, 2025-11-25, and 2026-07-28. All
three carry the QZX contract object in `structuredContent`, make its stable core
visible through MCP `outputSchema`, and keep completed failures consistent with
`isError`. Receipts record whether `outputSchema` embeds the canonical schema
(`canonical_ref`, `canonical_inline`, or `canonical_allof`) or uses the weaker,
SDK-portable `structural_core` mode whose submitted runtime evidence is validated
against the complete Result Contract. The 2026-07-28 profile additionally requires
`resultType: "complete"`; the two 2025 profiles do not invent that field because
MCP did not require it yet. Compatibility describes the result contract; it
does not imply endorsement, safe execution, or complete command parity.

The CLI validates its final envelope before printing it. Validate a saved or
piped document from a source checkout without a third-party dependency:

```bash
python scripts/validate_result_contract.py result.json
qzx getCurrentDateTime --output-format iso --json \
  | python scripts/validate_result_contract.py -
```

Run the positive and negative reference fixtures with:

```bash
python scripts/run_result_contract_conformance.py
```

Validate a completed MCP tool result and its tool definition with the
dependency-free MCP profile validator. It defaults to the newest supported
revision; use `--spec-version` when the evidence comes from an older MCP server:

```bash
python scripts/validate_mcp_result_contract.py mcp-result.json \
  --tool-definition mcp-tool-definition.json

python scripts/validate_mcp_result_contract.py mcp-result.json \
  --spec-version 2025-11-25 \
  --tool-definition mcp-tool-definition.json
```

For a reviewable implementation or pilot, validate one real success and one
real failure together and generate a deterministic receipt containing the input
SHA-256 digests plus fingerprints of the exact QZX contract schema, receipt
schema, core validator, MCP validator, and evidence validator used for the
verdict:

```bash
python scripts/validate_result_contract_evidence.py \
  --profile mcp-2026-07-28 \
  --success result-contract-evidence/success.json \
  --failure result-contract-evidence/failure.json \
  --tool-definition result-contract-evidence/tool-definition.json \
  --report result-contract-evidence/qzx-conformance.json
```

The generated receipt self-identifies the public
[QZX Result Contract Conformance Receipt v1 schema](https://qzx.yumbale.com/schemas/result-contract-conformance-receipt-v1.schema.json),
so its structure can be checked independently with JSON Schema 2020-12. Its
`validation_materials` fingerprints let reviewers tie the verdict to
byte-identical source artifacts from a pinned QZX revision. A schema-valid
receipt can still record failed conformance.

The same check is available as the reusable repository-root
[QZX Result Contract conformance Composite Action](action.yml) for external
GitHub repositories, so callers can use the normal `owner/repository@sha` form;
the Action also exposes the exact contract schema digest as
`contract_schema_sha256`. Independent implementations and bounded
pilots can follow the [adoption guide](docs/result-contract-adoption.md). If an
experiment is not ready for a formal adoption report, use the short
[Result Contract pilot or integration help form](https://github.com/alesanGreat/QZX-Quick-Zap-Exchange/issues/new?template=result_contract_pilot.yml)
to start with one real tool without claiming adoption. Organizations may also
[fund a bounded public interoperability pilot](https://qzx.yumbale.com/en/donate)
under the [sponsorship and independence policy](SPONSORSHIP.md). Funding a pilot
never counts as adoption or certification: only public, reviewable, authorized
independent evidence is listed in [ADOPTERS.md](ADOPTERS.md). QZX itself is the
reference implementation and is not counted as independent adoption.

The CLI prints `message` by default. Pass `--json` to print the complete
structured result:

```bash
qzx findFiles examples/qzx_in_action "*.txt" -r
qzx findFiles examples/qzx_in_action "*.txt" -r --json
```

Command lookup is case-insensitive. Documentation uses each command's canonical
lower-camel-case spelling.

### Golden Core is a focus cohort, not a maturity claim

The [QZX Golden Core](docs/golden-core.md) selects 15 high-frequency read-only
commands for deeper tests, contract review, captured evidence, and platform
validation. All selected commands remain Alpha until their individual evidence
supports promotion. Verify the packaged registry with:

```bash
python scripts/verify_golden_core.py
```

The repository's existing Windows, Linux, and macOS matrix also captures one
sanitized 15-command evidence record per runner and validates a combined
cross-platform summary. The capturer uses only disposable fixtures and an
authorized loopback HTTP endpoint; it does not request secrets or private
project data. Independent contributors can use the
[Golden Core platform evidence form](https://github.com/alesanGreat/QZX-Quick-Zap-Exchange/issues/new?template=golden_core_evidence.yml)
after manually reviewing the generated JSON for private data.

### Command maturity is explicit

Every installed command has an independent lifecycle assessment. `help`,
`listCommands`, direct `--json` output, and the public catalog expose whether
its contract is Alpha, Beta, Release Candidate, Stable, or Deprecated.
Planning and proof-of-concept work remains outside the executable command
loader, so an AI agent cannot mistake a roadmap intention for an installed
capability.

The initial assessment is deliberately conservative: existing public commands
start at Alpha until command-specific evidence supports promotion. Immutable
future release tags preserve the exact command-to-stage map shipped by that
version. See the [command lifecycle policy](docs/command-lifecycle.md).

## Good starting commands in this release

These names belong to this release's generated command index:

```bash
qzx version --json
qzx listCommands --json
qzx help findFiles
qzx getSystemInfo --json
qzx getCurrentDateTime --output-format iso --json
qzx findFiles . "*.py" -r --json
qzx findText "TODO" src -r --json
qzx getRamInfo --json
qzx getDiskSpace --json
qzx listProcesses "python" --json
```

Before a consequential operation, inspect the installed help and the
[command reference](https://qzx.yumbale.com/en/commands) for parameters,
platform availability, native dependencies, mutation classification, backup
requirements, and preview support.

## Develop QZX from source

The published package and the development checkout may differ while a new
release is being prepared. Ask the installed runtime for its actual command
catalog instead of assuming a command is present:

```bash
qzx version --json
qzx listCommands --json
```

Install the checkout for development:

```bash
python -m pip install -e .
python -m pytest -q
```

The repository launchers (`qzx.bat` and `qzx.sh`) can also run the checkout
directly. They prefer the standard CPython 3.13 runtime selected explicitly
with `QZX_PYTHON`, an active compatible environment, or an existing `uv`
installation. Ordinary invocations use a validated packaged command index and
import only the requested command; full discovery remains a development and CI
integrity check. The basic `qzx welcome` path avoids system, memory, and storage
probes; request those details explicitly with `qzx welcome true`.

Optional command groups can be installed with
`python -m pip install "qzx[filetype]"` or
`python -m pip install "qzx[ai]"`. Some operations also depend on host tools
such as Git, smartmontools, formatters, or language toolchains.

## Safety model

QZX executes with the permissions of the current user. Commands may mutate or
delete files, terminate processes, invoke native programs, access the network,
or require elevated privileges.

In the development checkout, commands marked dangerous must create a restorable
backup before a real filesystem mutation and abort when the backup fails.
Preview and read-only modes do not require a backup. Explicit bypasses
`--dangerously-bypass-approvals-and-sandbox`, `--yolo`, and
`QZX_SAFETY=YOLO` can skip that QZX backup barrier; they do not bypass
operating-system permissions or grant user authorization.

Review the [security model](https://qzx.yumbale.com/en/security) before
delegating mutating commands.

## Pseudonymous CLI telemetry

Telemetry is enabled by default and schedules at most one
`version_first_run` event per QZX version and random local installation
identifier. It sends random installation and event UUIDs, QZX/Python/OS
metadata, architecture, virtual-environment and known-CI flags. The server also
observes the request IP and receipt time.

It does not send command names, arguments, terminal input, paths, environment
values, usernames, hostnames, file contents, process lists, or hardware serial
numbers. Raw IPs are retained for 1,825 days. Network or storage failures never
change a command result.

Disable telemetry with either:

```bash
QZX_TELEMETRY=0 qzx welcome
DO_NOT_TRACK=1 qzx welcome
```

An explicit `QZX_TELEMETRY=1` takes precedence over `DO_NOT_TRACK=1`. See the
[complete telemetry and deletion policy](https://qzx.yumbale.com/en/security).

## Compatibility evidence

<!-- BEGIN GENERATED TEST ENVIRONMENTS -->

QZX's automated tests are based on Microsoft Windows Server 2025 (10.0.26100) (x64), Microsoft Windows Server 2025 (10.0.26100) (x64 host / x86 CPython), Microsoft Windows Server 2022 (10.0.20348) (x64), Microsoft Windows 11 Enterprise (10.0.26200) (arm64), Ubuntu 24.04.4 (x64), Ubuntu 24.04.4 (arm64), Ubuntu 22.04.5 (x64), macOS 26.4 (25E246) (arm64), macOS 15.7.7 (24G720) (arm64), macOS 15.7.7 (24G720) (x64 (Intel)), Debian 13.6 (amd64), Alpine Linux 3.24.1 (x86_64), FreeBSD 15.1-RELEASE (amd64), OpenBSD 7.9 (amd64), OmniOS r151054 LTS (x86_64), and Oracle Solaris 11.4 CBE (x86_64), using the standard CPython 3.13 build.

QZX is Alpha software. This list identifies the environments used by the test matrix; it does not report run outcomes or guarantee compatibility.

<!-- END GENERATED TEST ENVIRONMENTS -->

Mocked unit tests are not compatibility evidence. Platform claims require
real-system tests that exercise the installed native dependencies and QZX's
public interface; the distinction and review rules are documented in the
[test evidence policy](tests/README.md). Submit a canonical cohort capture
through the [Golden Core evidence form](https://github.com/alesanGreat/QZX-Quick-Zap-Exchange/issues/new?template=golden_core_evidence.yml),
or use the [general platform-evidence form](https://github.com/alesanGreat/QZX-Quick-Zap-Exchange/issues/new?template=compatibility_report.yml)
for any other command or bounded observation.

Complete local stdout snapshots identify their QZX version, Python version,
operating system, date, fixture, and exit code on the
[QZX in action](https://qzx.yumbale.com/en/qzx-in-action) page.

## Repository structure

- `src/qzx/resources/product-manifest.json` is the canonical product, release,
  output, Python-policy, and telemetry manifest.
- `src/qzx/resources/test-environments.json` is the result-neutral source for
  the operating systems, versions, architectures, and runtime used by the
  automated test matrix.
- `src/qzx/resources/command-index.json` is a generated, validated projection
  of the discovered command classes. It lets each invocation import only the
  requested command module; `scripts/sync_command_index.py` regenerates or
  verifies it.
- `src/qzx/_build_info.py` is the generated lightweight startup projection of
  the canonical product and lifecycle manifests;
  `scripts/sync_runtime_metadata.py` regenerates or verifies it.
- `src/qzx/commands/` contains command implementations.
- `tests/` contains the public automated Python test suite.
- `examples/` contains standalone usage examples.
- `docs/` contains public product philosophy and generated command references.
- `.github/` contains the public contribution, support, funding, issue, and CI
  configuration.

## Contributing

Start with the [contribution guide](CONTRIBUTING.md) and
[project philosophy](docs/philosophy.md). Preserve the structured output
contract, add proportional tests, and keep published and development
availability explicit. For usage help and the right route for questions, bugs,
or private reports, see the [support guide](.github/SUPPORT.md).

License: [Apache-2.0](LICENSE). The attribution notice is in [NOTICE](NOTICE).
See [how to contribute](CONTRIBUTING.md), [how to cite QZX](CITATION.cff),
[machine-readable CodeMeta 3.1](codemeta.json), the [security policy](SECURITY.md),
[QZX Core Guarantee](QZX_CORE_GUARANTEE.md),
[sponsorship independence policy](SPONSORSHIP.md), and
[name and trademark policy](TRADEMARKS.md). Project participation and direction
are documented in the [code of conduct](CODE_OF_CONDUCT.md),
[governance](GOVERNANCE.md), [authors and credits](AUTHORS.md), and
[public roadmap](ROADMAP.md).
