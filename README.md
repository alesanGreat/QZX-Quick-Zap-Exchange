# QZX — Quick Zap Exchange

QZX — Quick Zap Exchange, created and maintained by Alejandro Sánchez.

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

PyPI publishes QZX `0.2.2.0.1`, which requires Python 3.9 or newer. This
checkout matches that published version, and its generated catalog calculates
the current command totals from the discovered implementation.

| Source | Version | Python | Command surface |
|---|---:|---:|---|
| Published package and current checkout | `0.2.2.0.1` | `>=3.9` | See the generated command catalog |

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

## Good starting commands in PyPI 0.2.2.0.1

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
[complete telemetry and deletion policy](docs/telemetry.md).

## Compatibility evidence

The project targets Windows, Linux, and macOS. Targeting a platform is not the
same as proving every command on it. The repository workflow is configured for
Python 3.9–3.13 across `windows-latest`, `ubuntu-latest`, and `macos-latest`;
the documentation does not claim a successful hosted run without a public run
URL.

Complete local stdout snapshots identify their QZX version, Python version,
operating system, date, fixture, and exit code on the
[QZX in action](https://qzx.yumbale.com/en/qzx-in-action) page.

## Repository structure

- `src/qzx/resources/product-manifest.json` is the canonical product, release,
  output, compatibility, and telemetry manifest.
- `src/qzx/commands/` contains command implementations.
- `scripts/utils/generate_documentation.py` builds every documentation
  projection from the inspected implementation, wheel inventory, translations,
  explicit safety policies, captured evidence, and the strict `llms.txt`
  template.
- `WebsiteQZX/` contains the server-rendered bilingual public site.
- `docs/` contains the canonical development, release, production, privacy, and
  troubleshooting documentation.

Do not change versions, build or publish distributions, create tags, or deploy
from these instructions alone; those are independent release operations.

## Contributing

Start with [AGENTS.md](AGENTS.md), the
[command guide](docs/guides/building-great-commands.md), and the
[project philosophy](docs/philosophy.md). Preserve the structured output
contract, add proportional tests, and keep published and development
availability explicit.

License: [Apache-2.0](LICENSE). The attribution notice is in [NOTICE](NOTICE).
