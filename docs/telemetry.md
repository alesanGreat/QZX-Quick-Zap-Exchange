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

QZX emits two deliberately low-frequency event families:

1. **Version activation.** At most one `version_first_run` event for each QZX
   version and random local installation identifier.
2. **Closed 10-day usage windows.** Command invocations are first aggregated
   locally by UTC day. Windows are globally aligned to 10-day calendar blocks
   anchored at 2026-01-01. After a block closes, QZX attempts to send one
   previously unsent block when QZX next runs. An offline machine therefore
   does not generate background traffic merely because ten days elapsed.

A failed network attempt may remain pending and retry later, but telemetry
failure never changes the success, failure, standard output, structured result,
or exit status of the QZX command that caused the check.

### Version-activation payload

The allow-listed activation payload contains:

- telemetry schema version and event type;
- random event UUID and random local installation UUID;
- QZX version;
- Python version and implementation;
- operating-system family, release, and kernel description;
- CPU architecture;
- whether QZX is running inside a virtual environment;
- whether a known CI marker is active.

### Ten-day usage payload

A closed usage window contains only aggregates for commands actually observed
during that block:

- canonical QZX command name;
- invocation count;
- accumulated execution time and maximum observed execution time;
- total invocation count and number of active UTC days;
- counts/days where stdin/stdout represented an interactive TTY;
- counts/days where foreground-terminal state was observable and positive;
- counts/days where a coarse recent-OS-input signal was available and positive;
- QZX version used when the report was emitted and whether a known CI marker
  was active.

The server computes average duration from the accumulated time and count, then
uses these aggregates for the private Top-10 command rankings and for an
explainable Human Evidence Score. Timing is QZX's existing command-level
`meta.duration_ms`; commands are not instrumented individually.

The recent-input signal currently exists only where QZX can query a coarse OS
idle/input state safely. It is intentionally treated as one weak evidence
dimension: it does not reveal whether the input was keyboard, mouse, touch, or
synthetic input, and it is never treated as proof by itself.

### What QZX does not send

Neither event family contains:

- command arguments;
- terminal input or terminal output;
- filesystem paths;
- environment-variable values;
- usernames or hostnames;
- file names or file contents;
- process names or process lists;
- individual key values, key timing, mouse/pointer coordinates, trajectories,
  clicks, touch coordinates, or raw HID events;
- hardware serial numbers.

The command name itself is present only in the closed 10-day aggregate described
above. Individual command invocations never leave the machine as separate
telemetry events.

The receiving server also observes the request IP address and receipt time as a
normal consequence of receiving the HTTP request. The random installation UUID
is generated locally; it is not derived from hardware, a Windows SID, an
operating-system account, a hostname, or user files.

### Human Evidence Score

The private administration dashboard scores **evidence**, not identity. Its
versioned model keeps independent dimensions separate: external origin,
interactive terminal evidence, coarse recent-input evidence, persistence across
days, continuity across QZX versions, and an explicitly reserved independent
verification dimension. Recurrence alone cannot promote an installation to a
human tier, and no installation is called “verified” without an independent
verification signal. The dashboard exposes the dimension weights and aggregate
tier counts so the score remains auditable instead of becoming a black box.

The implementation is public at
[`src/qzx/telemetry.py`](../src/qzx/telemetry.py) and
[`src/qzx/usage_telemetry.py`](../src/qzx/usage_telemetry.py).

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

QZX keeps two small local JSON state files. `telemetry.json` owns the random
installation identifier plus version-activation delivery state.
`usage-telemetry.json` contains only daily command aggregates, coarse
interaction counters, sent 10-day period identifiers, and at most one exact
pending aggregate report.

Default directories are:

- Windows: `%LOCALAPPDATA%\qzx\`
- macOS: `~/Library/Application Support/qzx/`
- Linux and other Unix-like systems: `$XDG_STATE_HOME/qzx/` when
  `XDG_STATE_HOME` is set, otherwise `~/.local/state/qzx/`

Set `QZX_TELEMETRY_STATE_DIR` to move both local files to another directory.
They are ordinary local state; QZX does not bind them to a particular Windows
installation or credential store. Disabling telemetry stops both recording and
delivery; it does not require deleting the local files.

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

### Optional workflow feedback

The [project quickstart](https://qzx.yumbale.com/en/ai-agent-quickstart) and
[website diagnostic guide](https://qzx.yumbale.com/en/troubleshoot-website-dns-tls-http)
offer optional categorical feedback: helpful, blocked during installation,
blocked while running, or unclear results. Help remains available without a
response or account. Each choice gives an immediate relevant next step.

Only the selected closed category and workflow identifier travel through the
existing website analytics session, alongside its existing page and server-observed
metadata. The feature does not read or send terminal output, a project, an entered
destination, clipboard contents, free text, contact details or new fingerprints.
The immediate confirmation describes the choice, not successful server delivery;
the help remains useful offline and the existing bounded queue retries delivery.

Private reporting uses the latest received choice per exact browser session and
workflow in the selected period. It shows guide views, successful copies and
self-reported outcomes by source, tracked reference and original landing page,
without requiring a CLI activation. Percentages are withheld below five
respondents. No response is not failure, and views before feedback became
available are not unanswered invitations. These voluntary responses are not
independent execution evidence, representative satisfaction, installations or income.

The bug report link selects the repository's existing form. It never submits an
issue automatically or inserts local destinations or terminal output. A public
report requires GitHub sign-in and deliberate review by its sender.

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
