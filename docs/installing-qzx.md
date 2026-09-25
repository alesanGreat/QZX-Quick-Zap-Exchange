# Installing QZX without fighting your Python environment

QZX — Quick Zap Exchange, created and maintained by Alejandro Sánchez.

QZX is a standalone command-line application distributed through PyPI. Choose
the installation path that matches how you use Python rather than forcing QZX
into an environment that your operating system or another project manages.

For a multilingual, browser-first walkthrough that keeps installation, first-success,
compatibility, support, and professional-help paths together, use the
[QZX installation hub](https://qzx.yumbale.com/en/install). This document remains
the source-adjacent technical version of the same installation boundary.

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

## Installed, but the terminal cannot find `qzx`?

Use the recovery path for the installation you actually made. A missing launcher
on PATH is not proof that the package is absent. The
[installation hub's recovery section](https://qzx.yumbale.com/en/install#command-not-found)
provides the same decision path in every published website language.

### After a pip installation: keep the same interpreter

Run QZX as a Python module through the exact interpreter that ran
`python -m pip install --upgrade qzx`. This does not depend on the `qzx` launcher
being on PATH:

```bash
python -m qzx version --json
python -m qzx getCurrentDateTime --output-format iso --json
```

When installation used `python3` or `py -3.13`, use that same prefix in **every**
command, including pip and QZX. Do not install with one interpreter and try to
recover through another. An activated environment or an explicit Python path is
more reliable than guessing which of several installations the shell selected.

If the module command reports `No module named qzx`, activate the environment
where you installed QZX and inspect that interpreter before reinstalling:

```bash
python -m pip --version
python -m pip show qzx
```

If pip cannot find the package here, QZX is absent from this interpreter. If
`qzx version --json` and `python -m qzx version --json` show different versions,
the two entry points resolve different installations; update only the one you
intend to use. Do not replace system Python or delete another project's packages
to repair a launcher. An `externally-managed-environment` error still needs the
managed-environment guidance below, not an override.

After verification, open your own project folder and run
`python -m qzx diagnoseProject .` with the same pip-installed interpreter for a
useful read-only briefing. QZX does not execute the project's discovered test or
build scripts. Review returned personal paths before sharing a diagnostic.

### After a pipx installation: restore pipx's launcher

First run `pipx list`. If QZX is listed, run `pipx ensurepath`, follow its
instructions to refresh or reopen the terminal, and retry `qzx version --json`.
If QZX is not listed, use the pipx installation path above.

The system Python normally cannot import a package isolated by pipx.
**`python -m qzx` is not a pipx repair.** Also, `pipx run` evaluates a temporary
environment, not the installation shown by `pipx list`; a successful temporary
run does not prove that the existing launcher works.

These instructions use standard [Python module execution](https://docs.python.org/3/using/cmdline.html#cmdoption-m)
and [pip's interpreter selection](https://pip.pypa.io/en/stable/user_guide/#running-pip),
not a new QZX feature or an unpublished package version. See
[pipx's installation guidance](https://pipx.pypa.io/stable/installation/) for its
platform-specific PATH setup.

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
