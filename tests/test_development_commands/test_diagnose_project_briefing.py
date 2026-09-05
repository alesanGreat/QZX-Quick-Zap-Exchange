"""Project briefings remain useful to people and complete for automation."""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from qzx.cli import _render_human
from qzx.commands.development.diagnose_project import DiagnoseProjectCommand


def make_project(root):
    (root / "pyproject.toml").write_text(
        '[project]\nname = "briefing-demo"\n'
        'dependencies = ["packaging>=24"]\n'
        '[tool.pytest.ini_options]\ntestpaths = ["tests"]\n'
        '[tool.ruff]\ntarget-version = "py313"\n',
        encoding="utf-8",
    )
    (root / "tests").mkdir()


def test_human_report_prioritizes_actions_without_dumping_machine_fields(tmp_path):
    make_project(tmp_path)
    result = DiagnoseProjectCommand().execute(str(tmp_path))
    human = _render_human(result)
    assert "PROJECT BRIEFING" in human
    assert "Technologies: Python" in human
    assert "Dependencies: 1 unique declared package in 1 manifest" in human
    assert "Tests: configured, not run" in human
    assert "python -m pytest" in human
    assert "ruff check" in human
    assert "Next:" in human
    assert "Release readiness: NOT ASSESSED" in human
    assert "Unique Declared Package Count" not in human
    assert "Configured But Not Run" not in human
    assert result["details"]["dependencies"]["unique_packages"] == ["packaging"]
    assert result["details"]["summary"]["verification"]["release_readiness"] == "not_assessed"


def test_findings_are_ordered_by_severity_without_reordering_evidence(tmp_path):
    make_project(tmp_path)
    result = DiagnoseProjectCommand().execute(str(tmp_path))
    details = result["details"]
    issues = [
        {"severity": severity, "title": severity + " finding", "remediation": "Review it"}
        for severity in ("info", "low", "high", "medium")
    ]
    details["summary"]["issues"] = issues
    report = DiagnoseProjectCommand._render_report(details)
    positions = [report.index(f"[{severity.upper()}]") for severity in ("high", "medium", "low", "info")]
    assert positions == sorted(positions)
    assert [item["severity"] for item in issues] == ["info", "low", "high", "medium"]


@pytest.mark.parametrize("git_failure", ["error", "unavailable"])
def test_failed_git_status_is_unknown_never_clean(tmp_path, git_failure):
    make_project(tmp_path)

    class DiagnosisWithUnavailableGitStatus(DiagnoseProjectCommand):
        """Explicit deterministic Git boundary; no runtime dependency patching."""

        @staticmethod
        def _run_git(root, *args):
            if args[0] == "status":
                return {"status": git_failure, "error": "Git status could not read the index"}
            return {"status": "ok", "stdout": str(root) if "--show-toplevel" in args else "main"}

    result = DiagnosisWithUnavailableGitStatus().execute(str(tmp_path))
    git = result["details"]["version_control"]
    assert git["status"] == "error"
    assert git["clean"] is None
    assert git["changed_count"] is None
    assert git["untracked_count"] is None
    assert "Git: state unavailable" in result["report"]
    issues = result["details"]["summary"]["issues"]
    assert any(issue["code"] == "git_inspection_failed" for issue in issues)
    assert not any(issue["code"] == "git_worktree_changed" for issue in issues)


def test_partial_file_scan_and_read_errors_stay_visible(tmp_path):
    make_project(tmp_path)
    details = DiagnoseProjectCommand().execute(str(tmp_path))["details"]
    details["file_scan"].update(scan_complete=False, error_count=2)
    report = DiagnoseProjectCommand._render_report(details)
    assert "PARTIAL (limit reached)" in report
    assert "2 metadata reads failed" in report


def test_project_text_cannot_inject_terminal_controls_or_extra_commands(tmp_path):
    make_project(tmp_path)
    details = DiagnoseProjectCommand().execute(str(tmp_path))["details"]
    path = "Project\npretend-command\x1b[2J\u202e"
    details["path"] = path
    report = DiagnoseProjectCommand._render_report(details)
    assert "\x1b" not in report
    assert "\u202e" not in report
    assert "\npretend-command" not in report
    assert details["path"] == path  # Preserve the exact machine evidence.


def test_no_observed_issues_is_not_a_claim_that_tests_passed(tmp_path):
    make_project(tmp_path)
    details = DiagnoseProjectCommand().execute(str(tmp_path))["details"]
    details["summary"].update(
        status="no_issues_observed", issue_count=0, informational_count=0, issues=[]
    )
    report = DiagnoseProjectCommand._render_report(details)
    assert "No issues were observed within this inspection's scope" in report
    assert "Tests: configured, not run" in report
    assert "Inspection is not a test run" in report


def test_real_cli_has_readable_output_and_one_complete_json_document(tmp_path):
    make_project(tmp_path)
    source = Path(__file__).resolve().parents[2] / "src"
    environment = {
        **os.environ,
        "PYTHONPATH": str(source),
        "PYTHONDONTWRITEBYTECODE": "1",
        "QZX_TELEMETRY": "0",
    }
    before = {path.relative_to(tmp_path): path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    argv = [sys.executable, "-B", "-m", "qzx", "diagnoseProject", str(tmp_path)]
    options = dict(
        cwd=tmp_path, env=environment, capture_output=True, text=True,
        encoding="utf-8", check=False,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    human = subprocess.run(argv, **options)
    machine = subprocess.run([*argv, "--json"], **options)
    assert human.returncode == 0, human.stderr
    assert machine.returncode == 0, machine.stderr
    assert "PROJECT BRIEFING" in human.stdout
    result = json.loads(machine.stdout)
    assert result["success"] is True
    assert result["meta"]["command"] == "diagnoseProject"
    assert "PROJECT BRIEFING" in result["report"]
    assert result["details"]["technologies"] == ["Python"]
    assert result["details"]["summary"]["verification"]["release_readiness"] == "not_assessed"
    after = {path.relative_to(tmp_path): path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    assert before == after


def test_real_git_with_an_unreadable_index_is_not_reported_clean(tmp_path):
    make_project(tmp_path)
    initialized = subprocess.run(
        ["git", "init", "--quiet", str(tmp_path)],
        capture_output=True, text=True, encoding="utf-8", check=False,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    assert initialized.returncode == 0, initialized.stderr
    index = tmp_path / ".git" / "index"
    damaged_index = b"deliberately invalid index in an isolated test repository"
    index.write_bytes(damaged_index)
    result = DiagnoseProjectCommand().execute(str(tmp_path))
    assert result["success"] is True
    assert result["details"]["version_control"]["status"] == "error"
    assert result["details"]["version_control"]["clean"] is None
    assert "Git: state unavailable" in result["report"]
    assert any(issue["code"] == "git_inspection_failed" for issue in result["details"]["summary"]["issues"])
    assert index.read_bytes() == damaged_index
