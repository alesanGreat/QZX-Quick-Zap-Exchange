"""Safety and output-contract tests for runScript."""

import os
import sys

from qzx.commands.system.run_script import RunScriptCommand


def test_python_script_output_and_arguments_are_structured(tmp_path):
    script = tmp_path / "fixture.PY"
    script.write_text(
        "import sys\nprint('received', len(sys.argv) - 1)\n",
        encoding="utf-8",
    )

    result = RunScriptCommand().execute(str(script), "secret-value", "two")

    assert result["success"] is True
    assert result["execution"]["exit_code"] == 0
    assert result["stdout"]["text"].splitlines() == ["received 2"]
    assert result["stdout"]["truncated"] is False
    assert result["script"]["argument_count"] == 2
    assert result["script"]["argument_values_returned"] is False
    assert "secret-value" not in str(result)


def test_output_is_retained_up_to_the_explicit_limit(tmp_path):
    script = tmp_path / "noisy.py"
    script.write_text("print('X' * 100)\n", encoding="utf-8")
    command = RunScriptCommand()
    command.retained_output_bytes = 16

    result = command.execute(str(script))

    assert result["success"] is True
    assert result["stdout"]["bytes_produced"] == len(
        ("X" * 100 + os.linesep).encode()
    )
    assert result["stdout"]["bytes_retained"] == 16
    assert result["stdout"]["truncated"] is True


def test_timeout_is_structured_and_retains_partial_output(tmp_path):
    script = tmp_path / "slow.py"
    script.write_text(
        "import time\nprint('started', flush=True)\ntime.sleep(5)\n",
        encoding="utf-8",
    )
    command = RunScriptCommand()
    # Leave enough time for a fresh CPython process to start on a loaded CI
    # host while remaining far below the fixture's five-second sleep.
    command.timeout_seconds = 0.5

    result = command.execute(str(script))

    assert result["success"] is False
    assert result["error_code"] == "script_timeout"
    assert result["execution"]["timed_out"] is True
    assert result["stdout"]["text"].splitlines() == ["started"]


def test_unsupported_and_missing_scripts_fail_without_execution(tmp_path):
    unsupported = tmp_path / "script.exe"
    unsupported.write_bytes(b"not executable")

    unsupported_result = RunScriptCommand().execute(str(unsupported))
    missing_result = RunScriptCommand().execute(str(tmp_path / "missing.py"))

    assert unsupported_result["error_code"] == "unsupported_script_type"
    assert missing_result["error_code"] == "script_not_found"


def test_public_invoke_still_requires_explicit_bypass(tmp_path, monkeypatch):
    script = tmp_path / "fixture.py"
    script.write_text("print('should not run')\n", encoding="utf-8")
    monkeypatch.delenv("QZX_SAFETY", raising=False)

    result = RunScriptCommand().invoke([str(script)])

    assert result["success"] is False
    assert result["error_code"] == "approval_required"
    assert sys.executable
