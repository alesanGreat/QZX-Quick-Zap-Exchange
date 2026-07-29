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
[Recorded output](https://qzx.yumbale.com/en/qzx-in-action) ·
[Compatibility](https://qzx.yumbale.com/en/compatibility) ·
[Security and telemetry](https://qzx.yumbale.com/en/security) ·
[Documentación en español](https://qzx.yumbale.com/es/)

QZX is a local command interface, not a shell replacement, remote execution
service, or security sandbox. It reduces platform-specific branches only for
operations present in the installed command catalog.

## Install the published package

```bash
python -m pip install qzx
qzx qzxListCommands
qzx qzxHelp findFiles
qzx getCurrentDate
qzx getCurrentDate --json
```

PyPI publishes QZX `0.2.2.0.4` with Python `>=3.13` metadata.
The current checkout follows the same minimum.

QZX supports the standard CPython 3.13.x build. Other Python versions or
implementations may work, but experimental free-threaded CPython builds, PyPy,
and other implementations are not certified.

| Source | Version | Python | Command surface |
|---|---:|---:|---|
| Published package | `0.2.2.0.4` | `>=3.13`; standard CPython 3.13.x is certified | Capabilities reconciled with the official wheel |
| Current checkout | `0.2.2.0.4` | `>=3.13`; standard CPython 3.13.x is certified | See the generated command catalog |

PyPI is authoritative for what `pip install qzx` installs. The installed
runtime is authoritative for its own command list.

## Output contract

Every public command returns an object with at least:

- `success`: an explicit boolean outcome;
- `message`: a descriptive human-readable summary;
- command-specific evidence such as paths, counts, units, versions,
  diagnostics, causes, or remediation when available.

The CLI prints `message` by default. Pass `--json` to print the complete
structured result:

```bash
qzx findFiles examples/qzx_in_action "*.txt" -r --format name
qzx findFiles examples/qzx_in_action "*.txt" -r --format name --json
```

Command lookup is case-insensitive. Documentation uses the current canonical
lower-camel-case spelling and lists accepted aliases separately.

### Command maturity is explicit

Every installed command has an independent lifecycle assessment. `qzxHelp`,
`qzxListCommands`, direct `--json` output, and the public catalog expose whether
its contract is Alpha, Beta, Release Candidate, Stable, or Deprecated.
Planning and proof-of-concept work remains outside the executable command
loader, so an AI agent cannot mistake a roadmap intention for an installed
capability.

The initial assessment is deliberately conservative: existing public commands
start at Alpha until command-specific evidence supports promotion. Immutable
future release tags preserve the exact command-to-stage map shipped by that
version. See the [command lifecycle policy](docs/command-lifecycle.md).

## Good starting commands in PyPI 0.2.2.0.4

These names were verified in the official wheel:

```bash
qzx version --json
qzx qzxListCommands --json
qzx qzxHelp findFiles
qzx systemInfo --json
qzx getCurrentDate --json
qzx findFiles . "*.py" -r --json
qzx findText "TODO" src -r --json
qzx getRAMInfo --json
qzx getDiskInfo --json
qzx listProcesses "python" --json
```

Before a consequential operation, inspect the installed help and the
[command reference](https://qzx.yumbale.com/en/commands) for parameters,
platform availability, native dependencies, mutation classification, backup
requirements, and preview support.

## Development-only commands

The following examples require the development checkout and must not be
recommended after only `pip install qzx`:

```bash
qzx scanProject . --json
qzx projectDoctor . --json
qzx repairWorkspace . --json
qzx systemDoctor --json
qzx auditRepository . --json
```

Install the checkout for development:

```bash
python -m pip install -e .
python -m pytest -q
```

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
QZX_TELEMETRY=0 qzx Welcome
DO_NOT_TRACK=1 qzx Welcome
```

An explicit `QZX_TELEMETRY=1` takes precedence over `DO_NOT_TRACK=1`. See the
[complete telemetry and deletion policy](https://qzx.yumbale.com/en/security).

## Compatibility evidence

<!-- BEGIN GENERATED TEST ENVIRONMENTS -->

QZX's automated tests are based on Microsoft Windows Server 2025 (10.0.26100) (x64), Ubuntu 24.04.4 (x64), macOS 26.4 (25E246) (arm64), Alpine Linux 3.24.1 (x86_64), FreeBSD 15.1-RELEASE (amd64), OpenBSD 7.9 (amd64), OmniOS r151054 LTS (x86_64), and Oracle Solaris 11.4 CBE (x86_64), using the standard CPython 3.13 build.

QZX is Alpha software. This list identifies the environments used by the test matrix; it does not report run outcomes or guarantee compatibility.

<!-- END GENERATED TEST ENVIRONMENTS -->

Mocked unit tests are not compatibility evidence. Platform claims require
real-system tests that exercise the installed native dependencies and QZX's
public interface; the distinction and review rules are documented in the
[test evidence policy](tests/README.md).

Complete local stdout snapshots identify their QZX version, Python version,
operating system, date, fixture, and exit code on the
[QZX in action](https://qzx.yumbale.com/en/qzx-in-action) page.

## Repository structure

- `src/qzx/resources/product-manifest.json` is the canonical product, release,
  output, Python-policy, and telemetry manifest.
- `src/qzx/resources/test-environments.json` is the result-neutral source for
  the operating systems, versions, architectures, and runtime used by the
  automated test matrix.
- `src/qzx/commands/` contains command implementations.
- `tests/` contains the public automated Python test suite.
- `examples/` contains standalone usage examples.
- `docs/` contains public product philosophy and generated command references.
- `.github/` contains the public contribution, funding, issue, and CI
  configuration.

## Contributing

Start with the [contribution guide](CONTRIBUTING.md) and
[project philosophy](docs/philosophy.md). Preserve the structured output
contract, add proportional tests, and keep published and development
availability explicit.

License: [Apache-2.0](LICENSE). The attribution notice is in [NOTICE](NOTICE).
See [how to contribute](CONTRIBUTING.md), [how to cite QZX](CITATION.cff),
the [security policy](SECURITY.md), [QZX Core Guarantee](QZX_CORE_GUARANTEE.md),
[sponsorship independence policy](SPONSORSHIP.md), and
[name and trademark policy](TRADEMARKS.md). Project participation and direction
are documented in the [code of conduct](CODE_OF_CONDUCT.md),
[governance](GOVERNANCE.md), [authors and credits](AUTHORS.md), and
[public roadmap](ROADMAP.md).
