"""Executable adoption example: real CLI pages and hostile continuation metadata."""

import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "read_file_pages.py"
spec = importlib.util.spec_from_file_location("qzx_read_file_workflow_example", EXAMPLE)
workflow = importlib.util.module_from_spec(spec)
spec.loader.exec_module(workflow)


def _run(*arguments):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", QZX_TELEMETRY="0", DO_NOT_TRACK="1", PYTHONUTF8="1")
    return subprocess.run(
        [sys.executable, "-B", str(EXAMPLE), *arguments], capture_output=True, env=env,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def test_demo_executes_real_cli_and_verifies_exact_multilingual_text():
    result = _run("--demo", "--page-bytes", "32")
    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert summary["success"] is True
    assert summary["demo_verified"] is True
    assert summary["pages"] > 1
    assert summary["decoded_utf8_sha256"] == hashlib.sha256(workflow.DEMO_TEXT.encode()).hexdigest()


def test_emit_pages_is_explicit_and_round_trips_real_cli_content():
    result = _run("--demo", "--page-bytes", "32", "--emit-pages")
    assert result.returncode == 0, result.stderr
    records = [json.loads(line) for line in result.stdout.splitlines()]
    pages = [row["result"] for row in records if row.get("event") == "page"]
    assert "".join(row["content"] for row in pages) == workflow.DEMO_TEXT
    assert records[-1]["demo_verified"] is True


def test_known_legacy_file_uses_explicit_encoding(tmp_path):
    path = tmp_path / "Sánchez legacy.txt"
    text = "Diseño, automatización y café.\r\n"
    path.write_bytes(text.encode("cp1252"))
    result = _run(str(path), "--encoding", "cp1252", "--page-bytes", "8")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["decoded_utf8_sha256"] == hashlib.sha256(text.encode()).hexdigest()


def test_page_limit_is_a_failure_not_full_file_success():
    result = _run("--demo", "--page-bytes", "32", "--max-pages", "1")
    assert result.returncode == 1
    summary = json.loads(result.stdout)
    assert summary["success"] is False
    assert summary["error_code"] == "page_limit_reached"


def test_missing_file_is_an_explicit_cli_failure(tmp_path):
    result = _run(str(tmp_path / "absent.txt"))
    assert result.returncode == 1
    assert json.loads(result.stdout)["success"] is False


def test_old_package_is_detected_before_any_file_read():
    calls = []
    def old_help(arguments):
        calls.append(arguments)
        return {"success": True, "details": {"parameters": [{"name": "file_path"}]}}
    with pytest.raises(workflow.ReadWorkflowError, match="development checkout"):
        workflow.require_pagination(qzx_runner=old_help)
    assert calls == [["help", "readFile"]]


def _partial_page(path):
    token = "f" * 64
    return {
        "success": True, "content": "abc",
        "details": {
            "offset": 0, "bytes_consumed": 3, "read_complete": False,
            "fingerprint_token": token, "encoding": "utf-8",
            "next_read": {
                "file_path": str(path), "max_bytes": 8, "max_lines": None,
                "offset": 3, "encoding": "utf-8", "expected_fingerprint": token,
            },
        },
    }


@pytest.mark.parametrize("field,value", [
    ("file_path", "other.txt"), ("offset", 0), ("max_bytes", 64),
    ("max_lines", 1), ("encoding", "cp1252"), ("expected_fingerprint", None),
])
def test_untrusted_continuation_cannot_change_the_workflow(tmp_path, field, value):
    path = tmp_path / "data.txt"
    result = _partial_page(path)
    result["details"]["next_read"][field] = value
    with pytest.raises(workflow.ReadWorkflowError):
        list(
            workflow.read_pages(
                path, page_bytes=8, qzx_runner=lambda _args: result
            )
        )


def test_eof_page_cannot_silently_schedule_another_read(tmp_path):
    result = _partial_page(tmp_path / "data.txt")
    result["details"]["read_complete"] = True
    with pytest.raises(workflow.ReadWorkflowError, match="EOF"):
        list(
            workflow.read_pages(
                tmp_path / "data.txt",
                page_bytes=8,
                qzx_runner=lambda _args: result,
            )
        )


def test_consumer_independently_checks_cross_page_fingerprint(tmp_path):
    path = tmp_path / "data.txt"
    first = _partial_page(path)
    second = copy.deepcopy(first)
    second["details"].update(offset=3, fingerprint_token="a" * 64, read_complete=True, next_read=None)
    responses = iter([first, second])
    with pytest.raises(workflow.ReadWorkflowError, match="changed between pages"):
        list(
            workflow.read_pages(
                path,
                page_bytes=8,
                qzx_runner=lambda _args: next(responses),
            )
        )


def test_example_never_executes_a_shell_or_contacts_a_service():
    observed = {}
    def run(arguments, **kwargs):
        observed.update(argv=arguments, **kwargs)
        return subprocess.CompletedProcess(arguments, 0, b'{"success":true}', b"")
    assert workflow.run_qzx(
        ["help", "readFile"], process_runner=run
    )["success"] is True
    assert observed["shell"] is False
    assert observed["argv"][:4] == [sys.executable, "-B", "-m", "qzx"]
    assert observed["env"]["QZX_TELEMETRY"] == "0"
    assert observed["env"]["DO_NOT_TRACK"] == "1"
