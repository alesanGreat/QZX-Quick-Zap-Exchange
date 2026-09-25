"""Keep the optional briefing workflow manual, attributed and failure-aware."""
from pathlib import Path
import re

import yaml

EXAMPLE = Path(__file__).resolve().parents[1] / "examples/project_briefing"
# BaseLoader preserves `on` as text instead of YAML 1.1's boolean conversion.
WORKFLOW = yaml.load((EXAMPLE / "github-actions.yml").read_text(), Loader=yaml.BaseLoader)


def test_optional_workflow_is_manual_read_only_and_uses_reviewed_action_commits():
    assert list(WORKFLOW["on"]) == ["workflow_dispatch"]
    assert WORKFLOW["permissions"] == {"contents": "read"}
    job = WORKFLOW["jobs"]["briefing"]
    assert job["runs-on"] == "ubuntu-24.04"
    assert job["env"]["QZX_TELEMETRY"] == "0"
    actions = {s["uses"].split("@")[0]: s for s in job["steps"] if "uses" in s}
    assert set(actions) == {"actions/checkout", "actions/setup-python", "actions/upload-artifact"}
    for step in actions.values():
        assert re.fullmatch(r"[a-z/-]+@[a-f0-9]{40}", step["uses"])
    assert actions["actions/checkout"]["with"]["persist-credentials"] == "false"
    assert actions["actions/setup-python"]["with"]["python-version"] == "3.13"


def test_optional_workflow_retains_evidence_without_masking_an_inspection_failure():
    steps = WORKFLOW["jobs"]["briefing"]["steps"]
    inspection = next(s for s in steps if s.get("id") == "briefing")
    assert inspection["continue-on-error"] == "true"
    assert '-I .github/qzx/project_briefing.py "$GITHUB_WORKSPACE"' in inspection["run"]
    assert '--output "$RUNNER_TEMP/qzx-project-briefing"' in inspection["run"]
    upload = next(s for s in steps if s.get("uses", "").startswith("actions/upload-artifact@"))
    assert upload["if"] == "${{ always() && steps.briefing.outcome != 'skipped' }}"
    assert upload["with"]["path"] == "${{ runner.temp }}/qzx-project-briefing/"
    assert upload["with"]["retention-days"] == "7"
    assert upload["with"]["if-no-files-found"] == "error"
    assert steps[-1]["if"] == "${{ always() && steps.briefing.outcome != 'success' }}"
    assert steps[-1]["run"] == "exit 1"


def test_documentation_matches_the_version_and_privacy_of_the_copyable_example():
    doc = (EXAMPLE / "README.md").read_text(encoding="utf-8")
    workflow = (EXAMPLE / "github-actions.yml").read_text()
    assert "qzx==0.2.2.0.9" in doc and "qzx==0.2.2.0.9" in workflow
    assert "configured_not_run" in doc
    assert "not a new QZX command or a file installed by pip" in doc
    assert "optional Actions template does\nupload" in doc
    assert "has not been executed as a hosted\nGitHub Actions run" in doc
    assert "Alejandro Sánchez" in doc
    assert "/en/donate" in doc and "/en/professional-services#request" in doc
    assert "secrets." not in workflow
    for path in ("project_briefing.py", "github-actions.yml", "../../docs/installing-qzx.md"):
        assert (EXAMPLE / path).is_file()
