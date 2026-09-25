# Find what is using a port on Windows, Linux, or macOS with QZX

QZX — Quick Zap Exchange, created and maintained by Alejandro Sánchez.

Use this workflow when a development server, database, local API, container, or other service refuses to start because a TCP or UDP port is already in use. The goal is to identify the listener with evidence before changing process state.

Typical symptoms include messages such as `address already in use`, `port is already allocated`, or a local service unexpectedly binding the port you need.

## 1. Install or update QZX

```bash
python -m pip install --upgrade qzx
```

For an isolated CLI installation, use `pipx install qzx`. If pip reports an `externally-managed-environment`, prefer pipx rather than overriding the system Python. See the [installation guide](installing-qzx.md).

QZX remains Alpha software. Check the installed command contract before building long-lived automation:

```bash
qzx help inspectPort
```

## 2. Ask one cross-platform question

To find out what owns port 3000:

```bash
qzx inspectPort 3000 --json
```

The same QZX command works on supported Windows, Linux, and macOS environments. You do not need to branch your automation into a PowerShell recipe, a Linux-specific socket utility, and a macOS-specific process lookup just to answer the first diagnostic question.

For a PostgreSQL-style port, for example:

```bash
qzx inspectPort 5432 --json
```

Remove `--json` when you want the normal human-readable terminal presentation.

## 3. Read the result before acting

Start with these fields:

- `status`: `free` or `in_use` when QZX could complete the inspection.
- `port`: the exact local port inspected.
- `in_use`: boolean form of the occupancy result.
- `observed_pids`: the process IDs observed as owners when the operating system exposes them.
- `processes`: process evidence such as name, PID, creation time, executable, command line, username, and memory when the host permits QZX to read those details.
- `limitations`: evidence QZX could not obtain on the current host.
- `errors`: non-fatal process-detail errors collected during an otherwise useful inspection.

A successful diagnostic result means QZX completed the inspection. It does **not** mean the process is safe to terminate, unnecessary, or owned by the application you expected.

If the port is free, the structured result contains no owner. If the port is in use but the operating system does not expose an owning PID, QZX reports that limitation instead of inventing one.

## 4. Treat process identity as evidence, not permission

A PID can be reused after a process exits. If you intend to take a later action against a process, re-inspect the port immediately before that action and compare the current PID and process creation time with the evidence you reviewed.

`inspectPort` is deliberately read-only. It does not terminate the listener or change process state. QZX keeps diagnosis and mutation separate so an agent or operator can reason about the evidence first.

The repository's focused tests use real listening sockets and a controlled child process to verify that inspection detects occupancy without terminating the process: [`tests/test_system_commands/test_inspect_port.py`](../tests/test_system_commands/test_inspect_port.py).

## 5. Review output before sharing it

Port ownership can be harmless to inspect locally while the **result itself can contain sensitive context**.

Depending on operating-system permissions, `processes` may include:

- a full executable path;
- the process command line and its arguments;
- a local username;
- project or directory names embedded in arguments.

Some applications put tokens, credentials, URLs, customer identifiers, or other secrets in command-line arguments. Before pasting an `inspectPort` result into a public issue, chat, ticket, forum, or AI conversation, review and redact fields that are not necessary for the diagnosis.

Do not publish raw output merely because the command is read-only.

## 6. A practical decision sequence

Use the evidence in this order:

1. **Inspect** — run `qzx inspectPort PORT --json`.
2. **Confirm occupancy** — check `status` and `in_use`.
3. **Identify the owner** — review PID, process name, creation time, and executable when available.
4. **Decide whether it is expected** — a development server, database, VPN, container runtime, IDE helper, or system service may legitimately own the port.
5. **Re-inspect before any mutation** — do not rely on an old PID after time has passed.
6. **Change state separately** — stopping or terminating a process is a different operation with a different risk boundary; only do it when you understand the owner and consequences.
7. **Verify** — inspect the port again after an intentional change instead of assuming the port became free.

The important boundary is deliberate: **inspect → understand → decide → change separately → verify**.

## 7. Give an AI agent the useful evidence, not the whole machine

After reviewing the result for sensitive fields, a focused prompt can be as small as:

> I ran `qzx inspectPort 3000 --json`. The port is in use. Review the PID, process name, creation time, executable, limitations, and errors I provide. Explain the most likely ownership without assuming the process should be killed. Propose one read-only next check first. Treat missing fields as unknown, not as evidence that they do not exist.

This keeps the agent anchored to observable fields and avoids turning a simple port conflict into speculative process management.

## Why this workflow is useful

Port conflicts are a good example of QZX's core value: the *question* is the same across operating systems even when the native diagnostic vocabulary is not. QZX gives humans, scripts, CI jobs, and AI agents one command name and one structured result shape for the supported operation.

That does not make QZX a shell replacement or a security sandbox. It removes an avoidable operating-system branch from a common diagnostic workflow.

## Related resources

- [`inspectPort` command reference](https://qzx.yumbale.com/en/commands/inspect-port)
- [QZX command catalog](https://qzx.yumbale.com/en/commands)
- [Compatibility evidence](https://qzx.yumbale.com/en/compatibility)
- [Security and telemetry](https://qzx.yumbale.com/en/security)
- [AI-agent quickstart](https://qzx.yumbale.com/en/ai-agent-quickstart)
- [Professional services](https://qzx.yumbale.com/en/professional-services)
- [Support QZX development](https://qzx.yumbale.com/en/donate)

QZX is free and open source. If this workflow saves time and you want to help sustain its development, the support page lists optional ways to contribute. If you need to turn it into a production diagnostic, deployment gate, fleet workflow, or custom integration, Alejandro Sánchez also offers scoped professional work without changing QZX's free feature set.
