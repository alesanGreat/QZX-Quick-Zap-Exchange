# A project briefing you can keep, review and share

**QZX — Quick Zap Exchange, created and maintained by Alejandro Sánchez.**

Turn one read-only project inspection into a human briefing, complete JSON evidence
and a receipt with file sizes and SHA-256 hashes. Use it for onboarding, an AI-agent
handoff, or a first conversation about a legacy project. No account, API key, paid
feature or project dependency installation is required for the inspection itself.

This is a **copyable example**, not a new QZX command or a file installed by pip.
It uses `diagnoseProject` from the published **0.2.2.0.9** package. That is the
version verified for this example, not a promise that it remains the newest one.
QZX is Alpha software. No tests, linters, builds or discovered package scripts are
executed by that version's project diagnosis.

## Get a useful result locally

Keep `project_briefing.py` from this directory. Use Python 3.13, the interpreter
verified on Windows with the published package, in an environment you control. A dedicated
virtual environment avoids changing a system-managed Python:

```bash
python -m venv .qzx-briefing-venv
```

On Linux or macOS, use `.qzx-briefing-venv/bin/python` below. On Windows, use
`.qzx-briefing-venv\Scripts\python.exe`. These are commands, not activation scripts;
they also work when shell policy prevents activating an environment.

```bash
.qzx-briefing-venv/bin/python -I -m pip install --only-binary=:all: 'qzx==0.2.2.0.9'
.qzx-briefing-venv/bin/python -I project_briefing.py /path/to/project --output /path/to/new-briefing
```

Windows PowerShell example:

```powershell
.qzx-briefing-venv\Scripts\python.exe -I -m pip install --only-binary=:all: 'qzx==0.2.2.0.9'
.qzx-briefing-venv\Scripts\python.exe -I project_briefing.py 'C:\Projects\Example App' --output 'C:\Reports\Example App briefing'
```

Choose a **new** output directory **outside** the inspected project. An existing
directory is rejected; a previous report is never overwritten. The CLI prints the
chosen output path and a success/failure message rather than dumping project
observations into terminal or CI logs.

| File | What it preserves |
| --- | --- |
| `briefing.md` | Readable observations, explicit limitations and next steps, with project content kept literal |
| `diagnosis.json` | The command's complete, unmodified stdout; consult the receipt before assuming it is valid JSON |
| `diagnosis.stderr.txt` | Complete diagnostic stderr, which can be empty on success |
| `receipt.json` | QZX/Python versions, command exit status, export outcome and hashes of the other three files |

The receipt is written last. A missing receipt means the export itself did not
finish; do not treat partially written files as a completed report. Malformed or
incompatible command output is retained for investigation, but the export fails.
Hashes detect accidental changes relative to the receipt; they are **not** digital
signatures or proof of authorship against someone able to rewrite the receipt.

## Interpret the outcome correctly

An exit status of **0** means QZX completed the inspection and the evidence was
saved. Findings do not turn an otherwise completed inspection into a failed test
suite. The scan may still be bounded or partial: inspect `details.file_scan` in the
original diagnosis. Configured tests may still say `configured_not_run`.

An exit status of **1** means QZX failed, returned an unsuccessful result, or
produced an incompatible result. A nonzero command exit never becomes success just
because stdout contains `"success": true`. Status **2** indicates a usage or
filesystem problem, such as an existing output directory or a missing project.

**Release readiness stays NOT ASSESSED.** This report is an inventory and starting
point for review, not security certification, an executed test suite or deployment
approval. Review suggestions before running them. Isolated Python and an empty
working directory avoid imports from the inspected tree, but are not a sandbox
for hostile repositories.

## Use the same workflow in GitHub Actions

Copy these two files into a repository you own or maintain:

| From this example | Destination in your repository |
| --- | --- |
| `project_briefing.py` | `.github/qzx/project_briefing.py` |
| `github-actions.yml` | `.github/workflows/qzx-project-briefing.yml` |

The workflow appears after it is present on the default branch. Run **QZX project
briefing** manually from the Actions tab. The template uses GitHub-hosted Ubuntu
24.04, Python 3.13, a pinned published QZX version, read-only repository permission,
checkout without persisted credentials, and commit-pinned official actions. It
neither opens issues nor comments on pull requests. The example is not activated
in QZX's own release workflow merely by being stored here.

After the job, download the `qzx-project-briefing` artifact. It retains the report
for seven days and preserves evidence even when the inspection fails. The last
step still fails the job when inspection was unsuccessful: artifact upload is not
a passing diagnosis. There is deliberately no automatic schedule or pull-request
trigger. Decide when and where reports should be shared before adding automation.

The version/action pins make those selections explicit. They do not lock every
transitive dependency or the hosted runner image, and they are not a claim of
bit-for-bit reproducible execution. Review and retest updates rather than replacing
pins with `latest`. Source references for the verified action versions:
[checkout](https://github.com/actions/checkout),
[setup-python](https://github.com/actions/setup-python), and
[upload-artifact](https://github.com/actions/upload-artifact).

The template has been statically validated; it has not been executed as a hosted
GitHub Actions run in this validation. Local end-to-end evidence was produced on
Windows with CPython 3.13.13 and the hash-verified published QZX 0.2.2.0.9 wheel.
Do not interpret the Linux/macOS command examples as physical platform test evidence.

## Privacy and troubleshooting

The **local exporter** does not upload reports, send email or open issues. It turns
off QZX telemetry for the child process. The **optional Actions template does
upload** the four files to that repository's Actions artifacts; visibility follows
GitHub's repository/artifact access rules. A seven-day retention setting is not a
confidentiality guarantee. Paths, filenames and project observations may be
sensitive even though the verified command does not read environment-file values.
Review before sharing with a client, public issue, support service or external AI.

`No module named qzx` means the selected interpreter does not have QZX installed.
Install it using that interpreter's `-m pip`, not an unrelated global pip. For
system-managed Python and other installation problems, see the
[installation guide](../../docs/installing-qzx.md). A partial scan is not an export
failure: use the coverage fields and narrow the inspected directory when useful.

## Keep the value connected to its creator

Read the [project-briefing guide](../../docs/project-briefing.md) and
[meet Alejandro Sánchez](https://qzx.yumbale.com/en/alejandro-sanchez).
[Support QZX's development](https://qzx.yumbale.com/en/donate), or
[discuss an integration, automation or project workflow](https://qzx.yumbale.com/en/professional-services#request).
The report and its evidence remain free; donations do not unlock results and paid
professional work is a separate service.
