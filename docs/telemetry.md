# QZX telemetry and website analytics policy

QZX — Quick Zap Exchange is created and maintained by Alejandro Sánchez.

This document separates two different measurement surfaces that should not be
confused:

1. **QZX CLI telemetry** — a pseudonymous version-activation event emitted by
   the installed command-line application.
2. **QZX website analytics** — browser and server-side measurements used to
   understand whether the public website helps people discover, install, and
   use QZX.

The CLI telemetry controls described below do not disable ordinary analytics on
`qzx.yumbale.com`, because the website and the installed CLI are separate
systems.

## QZX CLI telemetry

CLI telemetry is enabled by default unless it is disabled through
`QZX_TELEMETRY=0` or `DO_NOT_TRACK=1`. An explicit `QZX_TELEMETRY=1` takes
precedence over `DO_NOT_TRACK=1`.

QZX schedules at most one `version_first_run` event for each QZX version and
random local installation identifier. A failed network attempt may remain
pending and retry later, but telemetry failure never changes the success,
failure, standard output, or structured result of the QZX command that caused
the check.

### What the CLI sends

The payload is allow-listed in `src/qzx/telemetry.py`. It contains:

- telemetry schema version;
- event type (`version_first_run`);
- random event UUID;
- random local installation UUID;
- QZX version;
- Python version and implementation;
- operating-system family, release, and kernel description;
- CPU architecture;
- whether QZX is running inside a virtual environment;
- whether a known CI marker is active.

The receiving server also observes the request IP address and receipt time as a
normal consequence of receiving the HTTP request.

The random installation UUID is generated locally. It is not derived from
hardware, a Windows SID, an operating-system account, a hostname, or user
files.

### What the CLI does not send

The CLI telemetry payload does **not** contain:

- QZX command names or arguments;
- terminal input;
- filesystem paths;
- environment-variable values;
- usernames or hostnames;
- file names or file contents;
- process lists;
- hardware serial numbers.

The implementation is public at
[`src/qzx/telemetry.py`](../src/qzx/telemetry.py).

## Disable CLI telemetry

For one invocation or a process environment:

```bash
QZX_TELEMETRY=0 qzx welcome
```

QZX also respects:

```bash
DO_NOT_TRACK=1 qzx welcome
```

An explicit `QZX_TELEMETRY=1` overrides `DO_NOT_TRACK=1`.

## Local telemetry state

QZX keeps a small local JSON state file so it can generate a random
installation identifier, avoid repeatedly sending the same version activation,
and remember pending delivery state.

Default locations are:

- Windows: `%LOCALAPPDATA%\qzx\telemetry.json`
- macOS: `~/Library/Application Support/qzx/telemetry.json`
- Linux and other Unix-like systems: `$XDG_STATE_HOME/qzx/telemetry.json` when
  `XDG_STATE_HOME` is set, otherwise `~/.local/state/qzx/telemetry.json`

Set `QZX_TELEMETRY_STATE_DIR` to move this local state to another directory.
The file is ordinary local state; QZX does not bind it to a particular Windows
installation or credential store.

## Retention and deletion

The current QZX product policy retains raw IP addresses associated with CLI
telemetry for **1,825 days**. This value is part of the public product manifest
and may change only through an explicit public policy update.

A private deletion request requires the random installation UUID from the local
telemetry state. Send the request to `qzx@yumbale.com`. Do not post an
installation UUID in a public issue.

## Website analytics are separate

The public QZX website records pageviews, session engagement, browser
performance signals, and selected product interactions so the project can
measure acquisition and product usefulness without treating traffic as
adoption.

For installation choices, the website records short labels such as
`copy_install_command` and a route target (`pip`, `pipx`, or a temporary
`pipx run` evaluation path). A copy conversion is recorded only after the
browser reports a successful copy operation.

These browser events do **not** contain the copied command or clipboard
contents. They also do not contain terminal input, project contents, or files
from the user's machine.

QZX keeps website synthetic health checks segregated from real product signals
so deployment tests do not masquerade as user adoption.

The public, bilingual disclosure for website analytics and CLI telemetry is the
[QZX security page](https://qzx.yumbale.com/en/security).

## Why QZX measures this

The project uses these signals to answer bounded product questions such as:

- Did a visitor reach an installation path?
- Which documented installation route was successfully copied?
- Did an attributable external QZX activation later appear?
- Are documentation, compatibility, or onboarding changes helping real use?

A copied command is **not** counted as an installation, and a PyPI download is
**not** treated as a person. Where QZX correlates website intent with later CLI
activation, the result is reported as inferred attribution rather than a known
identity.

## References

- [QZX security model](https://qzx.yumbale.com/en/security)
- [QZX source implementation](../src/qzx/telemetry.py)
- [QZX product manifest](../src/qzx/resources/product-manifest.json)
- [QZX installation guide](installing-qzx.md)
- Contact: `qzx@yumbale.com`
