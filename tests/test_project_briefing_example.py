"""The copyable project-briefing example must preserve evidence and failure."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

SOURCE = Path(__file__).resolve().parents[1] / "examples/project_briefing/project_briefing.py"
spec = importlib.util.spec_from_file_location("qzx_briefing_example", SOURCE)
briefing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(briefing)


def result(**updates):
    value = {
        "success": True, "message": "Inspection completed with findings.",
        "report": "PROJECT BRIEFING\n3 findings\nTests: discovered, not run.",
        "details": {"file_scan": {"scan_complete": False},
                    "summary": {"issues": [{"code": "example"}] * 3}},
    }
    return {**value, **updates}


@pytest.fixture
def runtime(tmp_path):
    project = tmp_path / "project with spaces and á"
    project.mkdir()
    (project / "README.md").write_text("Original project bytes.\n", encoding="utf-8")
    state = {"stdout": json.dumps(result()).encode(), "stderr": b"", "code": 0,
             "calls": [], "project": project, "output": tmp_path / "briefing"}

    def invoke(command, **options):
        state["calls"].append((command, options))
        if "exception" in state:
            raise state["exception"]
        options["stdout"].write(state["stdout"])
        options["stderr"].write(state["stderr"])
        return SimpleNamespace(returncode=state["code"])

    state["process_runner"] = invoke
    state["version_reader"] = lambda _: "0.2.2.0.9"
    return state


def collect(runtime):
    return briefing.collect(
        runtime["project"],
        runtime["output"],
        process_runner=runtime["process_runner"],
        version_reader=runtime["version_reader"],
    )


def test_complete_json_and_partial_scan_are_preserved_without_claiming_tests_passed(runtime):
    original = runtime["stdout"]
    receipt = collect(runtime)
    output = runtime["output"]
    assert receipt["success"] is True
    assert (output / "diagnosis.json").read_bytes() == original
    evidence = json.loads((output / "diagnosis.json").read_bytes())
    assert evidence["details"]["file_scan"]["scan_complete"] is False
    assert len(evidence["details"]["summary"]["issues"]) == 3
    assert receipt["details"]["release_readiness"] == "not_assessed"
    assert "tests were not run" in receipt["message"]
    assert (runtime["project"] / "README.md").read_text() == "Original project bytes.\n"
    assert [p.name for p in runtime["project"].iterdir()] == ["README.md"]
    for name, description in receipt["details"]["files"].items():
        data = (output / name).read_bytes()
        assert description == {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
    assert json.loads((output / "receipt.json").read_text(encoding="utf-8")) == receipt


def test_subprocess_uses_an_argument_array_isolated_interpreter_and_external_cwd(runtime):
    collect(runtime)
    command, options = runtime["calls"][0]
    assert command == [briefing.sys.executable, "-I", "-m", "qzx", "diagnoseProject",
                       str(runtime["project"].resolve()), "--json"]
    assert options["cwd"] == runtime["output"]
    assert options.get("shell", False) is False
    assert options["stdin"] == subprocess.DEVNULL
    assert options["env"]["QZX_TELEMETRY"] == "0"
    assert options["env"]["DO_NOT_TRACK"] == "1"
    assert options["env"]["PYTHONDONTWRITEBYTECODE"] == "1"


@pytest.mark.parametrize("raw", [
    b"not JSON", b"[]", b"null", b'{"success":"true","message":"ok"}',
    b'{"success":true,"message":"ok"}',
    b'{"success":true,"message":"ok","report":""}',
    b'{"success":true,"message":"","report":"ok"}',
    b'{"success":true,"success":false,"message":"ok","report":"ok"}',
    b'{"success":true,"message":"ok","report":"ok","value":NaN}',
    b"\xff\xfe\xff", b"",
])
def test_invalid_or_incompatible_output_is_saved_but_never_passes(runtime, raw):
    runtime["stdout"] = raw
    receipt = collect(runtime)
    assert receipt["success"] is False
    assert receipt["error_code"] == "project_briefing_failed"
    assert receipt["details"]["project_result_readable"] is False
    assert (runtime["output"] / "diagnosis.json").read_bytes() == raw
    assert "did not complete successfully" in (runtime["output"] / "briefing.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("code,success", [(7, True), (0, False), (3, False), (-9, True)])
def test_failed_exit_or_failed_result_never_becomes_a_successful_export(runtime, code, success):
    runtime["code"] = code
    runtime["stdout"] = json.dumps(result(success=success)).encode()
    runtime["stderr"] = b"diagnostic\r\n"
    receipt = collect(runtime)
    assert receipt["success"] is False
    assert receipt["details"]["command_returncode"] == code
    assert f"exit status: {code}" in receipt["details"]["reason"]
    assert (runtime["output"] / "diagnosis.stderr.txt").read_bytes() == b"diagnostic\r\n"


def test_failed_result_does_not_need_a_success_report(runtime):
    runtime["stdout"] = b'{"success":false,"message":"The directory cannot be read."}'
    receipt = collect(runtime)
    assert receipt["success"] is False
    assert receipt["details"]["project_result_readable"] is True
    assert "The directory cannot be read." in (runtime["output"] / "briefing.md").read_text(encoding="utf-8")


def test_launch_failure_keeps_evidence_and_a_failure_receipt(runtime):
    runtime["exception"] = FileNotFoundError("Python executable unavailable")
    receipt = collect(runtime)
    assert receipt["success"] is False
    assert receipt["details"]["command_returncode"] is None
    assert "FileNotFoundError" in receipt["details"]["reason"]


def test_existing_directory_is_never_overwritten(runtime):
    runtime["output"].mkdir()
    sentinel = runtime["output"] / "receipt.json"
    sentinel.write_bytes(b"existing evidence")
    with pytest.raises(FileExistsError):
        collect(runtime)
    assert sentinel.read_bytes() == b"existing evidence"
    assert runtime["calls"] == []


@pytest.mark.parametrize("same", [False, True])
def test_output_inside_project_is_rejected_before_any_write(runtime, same):
    runtime["output"] = runtime["project"] if same else runtime["project"] / "reports"
    with pytest.raises(ValueError, match="outside"):
        collect(runtime)
    assert runtime["calls"] == []
    assert [p.name for p in runtime["project"].iterdir()] == ["README.md"]


def test_missing_project_is_rejected_before_creating_output(runtime):
    runtime["project"] = runtime["project"] / "missing"
    with pytest.raises(FileNotFoundError):
        collect(runtime)
    assert not runtime["output"].exists()
    assert runtime["calls"] == []


def test_report_markup_stays_literal_and_cannot_inject_a_closing_fence():
    report = "```\n<script>example</script>\n```\n::error::literal\n\x1b[31mred"
    markdown = briefing._markdown(report, True)
    assert "````text\n```\n<script>" in markdown
    assert "\\u001b[31mred\n````" in markdown
    assert "Alejandro Sánchez" in markdown
    assert "https://qzx.yumbale.com/en/donate" in markdown
    assert "https://qzx.yumbale.com/en/professional-services#request" in markdown


@pytest.mark.parametrize("code,expected", [(0, 0), (7, 1)])
def test_cli_exit_preserves_command_outcome_without_printing_report_content(runtime, capsys, code, expected):
    runtime["code"] = code
    assert briefing.main(
        [str(runtime["project"]), "--output", str(runtime["output"])],
        process_runner=runtime["process_runner"],
        version_reader=runtime["version_reader"],
    ) == expected
    captured = capsys.readouterr()
    message = json.loads(captured.out)
    assert message["success"] is (expected == 0)
    assert "3 findings" not in captured.out


def test_cli_usage_failure_is_explicit(runtime, capsys):
    assert briefing.main([str(runtime["project"]), "--output", str(runtime["project"])]) == 2
    assert "outside the inspected project" in capsys.readouterr().err
