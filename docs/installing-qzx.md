# Installing QZX without fighting your Python environment

QZX — Quick Zap Exchange, created and maintained by Alejandro Sánchez.

QZX is a standalone command-line application distributed through PyPI. Choose
the installation path that matches how you use Python rather than forcing QZX
into an environment that your operating system or another project manages.

## Choose the right path

| Situation | Recommended command |
|---|---|
| You want QZX as an isolated CLI | `pipx install qzx` |
| You already have an activated virtual environment or otherwise control the current Python environment | `python -m pip install --upgrade qzx` |
| You already have pipx and only want to try QZX without keeping it | `pipx run --spec qzx qzx version` |

All three routes resolve the published `qzx` package from PyPI. The installed
runtime remains authoritative for its own version and command catalog.

## Recommended isolated CLI install

[pipx](https://pipx.pypa.io/stable/) installs Python applications in dedicated
virtual environments and exposes their commands on your PATH. That keeps QZX's
Python dependencies separate from application projects and from other Python
CLIs.

```bash
pipx install qzx
qzx version --json
qzx getCurrentDateTime --output-format iso --json
```

To update or remove that installation later:

```bash
pipx upgrade qzx
pipx uninstall qzx
```

If the `qzx` command is not visible immediately after installing with pipx, run
`pipx ensurepath` and follow pipx's instruction for reopening or refreshing your
shell.

## Install into a Python environment you control

When QZX belongs in the currently selected Python environment, pip remains a
valid and intentionally supported route:

```bash
python -m pip install --upgrade qzx
qzx version --json
```

A project virtual environment is a good example because its dependencies are
already isolated from the operating-system Python.

## If pip says `externally-managed-environment`

Some current Linux distributions and package-manager Python installations mark
their base interpreter as externally managed. That protection means the base
Python is not the right place for an ordinary pip application install.

Do not work around that protection with `sudo pip`, `--break-system-packages`,
by deleting an `EXTERNALLY-MANAGED` marker, or by changing ownership of the
managed Python directories. Install pipx through the method supported by your
platform, then install QZX with:

```bash
pipx install qzx
```

The official [pipx installation guide](https://pipx.pypa.io/stable/installation/)
contains current Windows, macOS, and Linux setup instructions.

## Verify before delegating work

Whichever installation route you choose, make the installed runtime prove what
it is before an agent or script depends on it:

```bash
qzx version --json
qzx getCurrentDateTime --output-format iso --json
qzx listCommands file
qzx help findFiles
```

`qzx version --json` is the source of truth for the local installed version.
`listCommands` and `help` describe the command surface that machine can actually
execute.

## Current distribution boundary

QZX currently publishes its end-user Python package on PyPI and requires Python
3.11 or newer. Native standalone `.exe`, macOS application bundles, Homebrew
formulae, and Linux distribution packages are not currently advertised as
published QZX channels. Do not rely on an unofficial binary as if it were a QZX
release.

See the [compatibility page](https://qzx.yumbale.com/en/compatibility) for the
current platform evidence and the [security page](https://qzx.yumbale.com/en/security)
for telemetry and trust-boundary details.

QZX is free and open source. If it saves you time, you can
[support its development](https://qzx.yumbale.com/en/donate), or
[work with Alejandro Sánchez](https://qzx.yumbale.com/en/professional-services#request)
on integrations, automation, and engineering work.
