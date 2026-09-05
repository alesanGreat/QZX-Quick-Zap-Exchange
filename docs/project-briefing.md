# Understand an unfamiliar project with QZX

QZX — Quick Zap Exchange, created and maintained by Alejandro Sánchez.

Use this workflow when joining a codebase, handing a project to an AI agent, or
checking what needs attention before you run its scripts. It needs no account,
API key, or paid feature. QZX remains Alpha software.

## Install and confirm your version

```bash
python -m pip install --pre --upgrade qzx
qzx version --json
```

`--pre` opts into the Alpha channel documented here. A normal installation can
select an older final package. This does not imply that the final package has a
Stable command contract.

## Get the briefing

Run these commands from the project root, not from the QZX installation folder:

```bash
qzx diagnoseProject .
qzx getProjectTree . 2 --max_entries 200
qzx projectLanguages .
```

`diagnoseProject` produces a readable briefing with technologies, dependency
counts, Git state, file-scan coverage, findings ordered by severity, and a next
step for each finding. Discovered test, lint, type-check and build commands are
listed separately as **not run**. The bounded tree helps locate the relevant
files, and the language inventory helps choose appropriate tools.

A configured workflow is not a passing workflow. Read any project-owned scripts
before running the suggested commands. QZX does not execute those scripts as
part of this inspection, install dependencies, or change the project.

A file scan that reaches its limit or cannot read metadata is identified as
partial or incomplete in its evidence. Unavailable Git state is not a clean
working tree. Static unused-code candidates require manual review, especially
with dynamic imports or framework registration.

## Give an agent complete evidence

The human report does not replace or reduce the structured result:

```bash
qzx diagnoseProject . --json
qzx getProjectTree . 2 --max_entries 200 --json
qzx projectLanguages . --json
```

For `diagnoseProject`, inspect these fields:

| Field | Meaning |
| --- | --- |
| `success` | Whether the inspection completed, not whether the project passed tests |
| `message` | A short summary of the diagnosis |
| `report` | The human-readable briefing derived from the same evidence |
| `details.summary.issues` | Findings with severity, evidence description and remediation |
| `details.summary.verification.suggested_commands` | Discovered commands to review before execution |
| `details.summary.verification.release_readiness` | `not_assessed`; inspection does not certify a release |
| `details.file_scan` | File counts, scan coverage and metadata errors |
| `details.version_control` | Observed Git state, or an explicit unavailable/error result |

For the tree, check `details.scan_complete` before treating the displayed tree
as complete. Read the installed `qzx help projectLanguages` for the language
inventory's limits and classification of supporting formats.

A useful instruction for an agent is:

> Inspect this project with QZX first. Separate observed facts from suggested
> checks that have not run. Summarize the highest-priority findings and propose
> the smallest useful next change. Do not execute project scripts or remove
> unused-code candidates just because the inspection discovered them.

## Consume the result from Python

Use the same Python interpreter that has QZX installed. An argument array keeps
paths containing spaces intact without relying on shell quoting:

```python
import json
from pathlib import Path
import subprocess
import sys

project = Path(".").resolve()
completed = subprocess.run(
    [sys.executable, "-m", "qzx", "diagnoseProject", str(project), "--json"],
    capture_output=True,
    text=True,
    encoding="utf-8",
    check=False,
)
try:
    result = json.loads(completed.stdout)
except json.JSONDecodeError as exc:
    raise RuntimeError("QZX did not return a JSON result") from exc
if not isinstance(result, dict) or result.get("success") is not True:
    message = result.get("message", "Diagnosis failed") if isinstance(result, dict) else "Invalid QZX result"
    raise RuntimeError(message)
if completed.returncode != 0:
    raise RuntimeError(f"QZX exited with status {completed.returncode}")

for issue in result["details"]["summary"]["issues"]:
    print(f"{issue['severity']}: {issue['title']}")
    print(f"  Next: {issue['remediation']}")
```

The report contains project paths and observations. Review it before posting it
publicly or sending it to an external service.

## Go further

Read the [complete command reference](https://qzx.yumbale.com/en/commands) or the
[AI-agent quickstart](https://qzx.yumbale.com/en/ai-agent-quickstart). For bugs or
questions, use the [support guide](../.github/SUPPORT.md).

QZX is free. [Support its development](https://qzx.yumbale.com/en/donate),
[meet Alejandro Sánchez](https://qzx.yumbale.com/en/alejandro-sanchez), or
[discuss a custom automation or integration](https://qzx.yumbale.com/en/professional-services#request).
Donations do not unlock features; professional work is a separate service.
