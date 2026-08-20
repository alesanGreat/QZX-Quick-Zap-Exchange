"""Safety and output-contract tests for runScript."""

import os
import sys
import time

from qzx.commands.system import run_script as run_script_module
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
    assert result["stdout"]["capture_complete"] is True
    assert result["script"]["argument_count"] == 2
    assert result["script"]["argument_values_in_metadata"] is False
    assert result["script"]["captured_output_may_contain_argument_values"] is True
    assert "secret-value" not in str(result)


def test_public_success_omits_null_failure_fields(tmp_path, monkeypatch):
    script = tmp_path / "success.py"
    script.write_text("print('completed')\n", encoding="utf-8")
    monkeypatch.delenv("QZX_SAFETY", raising=False)

    result = RunScriptCommand().invoke([str(script), "--yolo"])

    assert result["success"] is True
    assert "error" not in result
    assert "error_code" not in result
    assert result["stdout"]["text"].splitlines() == ["completed"]


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


def test_multi_megabyte_output_is_drained_without_unbounded_retention(tmp_path):
    script = tmp_path / "large_output.py"
    output_size = 5 * 1024 * 1024
    script.write_text(
        "import sys\n"
        f"sys.stdout.buffer.write(b'X' * {output_size})\n",
        encoding="utf-8",
    )
    command = RunScriptCommand()
    command.retained_output_bytes = 1024

    result = command.execute(str(script))

    assert result["success"] is True
    assert result["stdout"]["bytes_produced"] == output_size
    assert result["stdout"]["bytes_retained"] == 1024
    assert result["stdout"]["capture_complete"] is True
    assert result["stdout"]["truncated"] is True
    assert result["stdout"]["text"] == "X" * 1024


def test_script_metadata_survives_self_deletion(tmp_path):
    script = tmp_path / "self_delete.py"
    script.write_text(
        "from pathlib import Path\n"
        "Path(__file__).unlink()\n"
        "print('removed')\n",
        encoding="utf-8",
    )
    original_size = script.stat().st_size

    result = RunScriptCommand().execute(str(script))

    assert result["success"] is True
    assert result["stdout"]["text"].splitlines() == ["removed"]
    assert result["script"]["size_bytes"] == original_size
    assert not script.exists()


def test_windows_process_group_flags_also_suppress_console_windows(monkeypatch):
    monkeypatch.setattr(run_script_module.os, "name", "nt")
    monkeypatch.setattr(
        run_script_module.subprocess,
        "CREATE_NEW_PROCESS_GROUP",
        0x00000200,
        raising=False,
    )
    monkeypatch.setattr(
        run_script_module.subprocess,
        "CREATE_NO_WINDOW",
        0x08000000,
        raising=False,
    )

    options = RunScriptCommand._process_group_options()

    assert options == {"creationflags": 0x08000200}


def test_timeout_is_structured_and_retains_partial_output(tmp_path):
    script = tmp_path / "slow.py"
    script.write_text(
        "import time\nprint('started', flush=True)\ntime.sleep(5)\n",
        encoding="utf-8",
    )
    command = RunScriptCommand()
    # Leave enough time for a fresh CPython process to start from a synced or
    # loaded Windows checkout while remaining well below the fixture's
    # five-second sleep.
    command.timeout_seconds = 2

    result = command.execute(str(script))

    assert result["success"] is False
    assert result["error_code"] == "script_timeout"
    assert result["execution"]["timed_out"] is True
    assert result["execution"]["termination"]["root_process_stopped"] is True
    assert result["stdout"]["text"].splitlines() == ["started"]


def test_timeout_terminates_a_spawned_child_process(tmp_path):
    marker = tmp_path / "child-survived.txt"
    child = tmp_path / "child.py"
    child.write_text(
        "import pathlib, sys, time\n"
        "time.sleep(4)\n"
        "pathlib.Path(sys.argv[1]).write_text('survived', encoding='utf-8')\n",
        encoding="utf-8",
    )
    parent = tmp_path / "parent.py"
    parent.write_text(
        "import subprocess, sys, time\n"
        "subprocess.Popen([sys.executable, sys.argv[1], sys.argv[2]])\n"
        "print('spawned', flush=True)\n"
        "time.sleep(20)\n",
        encoding="utf-8",
    )
    command = RunScriptCommand()
    command.timeout_seconds = 2

    result = command.execute(str(parent), str(child), str(marker))

    assert result["success"] is False
    assert result["error_code"] == "script_timeout"
    assert result["stdout"]["text"].splitlines() == ["spawned"]
    assert result["execution"]["termination"]["process_tree_confirmed"] is True
    assert result["execution"]["termination"]["root_process_stopped"] is True
    time.sleep(4.5)
    assert not marker.exists()


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
