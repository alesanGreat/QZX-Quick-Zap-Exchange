"""Contract tests for the installed-wheel smoke harness and CI wiring."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPOSITORY_ROOT / "scripts" / "smoke_installed_distribution.py"
WORKFLOW_PATH = REPOSITORY_ROOT / ".github" / "workflows" / "test.yml"


def _load_smoke_module():
    spec = importlib.util.spec_from_file_location(
        "qzx_smoke_installed_distribution",
        SCRIPT_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_subprocess_environment_removes_ambient_python_injection():
    smoke = _load_smoke_module()
    environment = smoke._subprocess_environment(
        {
            "PYTHONHOME": "ambient-home",
            "PYTHONINSPECT": "1",
            "PYTHONPATH": "ambient-path",
            "PYTHONSTARTUP": "ambient-startup.py",
            "PATH": "kept",
        }
    )

    assert "PYTHONHOME" not in environment
    assert "PYTHONINSPECT" not in environment
    assert "PYTHONPATH" not in environment
    assert "PYTHONSTARTUP" not in environment
    assert environment["PATH"] == "kept"
    assert environment["PYTHONDONTWRITEBYTECODE"] == "1"
    assert environment["PYTHONNOUSERSITE"] == "1"
    assert environment["QZX_TELEMETRY"] == "0"


def test_cli_probe_uses_python_isolated_mode(tmp_path):
    smoke = _load_smoke_module()
    calls = []

    def fake_run(command, *, cwd=None):
        calls.append((command, cwd))
        return type(
            "Completed",
            (),
            {"returncode": 0, "stdout": '{"success": true}', "stderr": ""},
        )()

    payload = smoke._invoke_qzx_json(
        ["clearScreen"],
        cwd=tmp_path,
        runner=fake_run,
    )

    assert payload == {"success": True}
    assert calls == [
        (
            [
                smoke.sys.executable,
                "-I",
                "-B",
                "-m",
                "qzx",
                "clearScreen",
                "--json",
            ],
            tmp_path,
        )
    ]

def test_wheel_discovery_requires_exactly_one_artifact(tmp_path):
    smoke = _load_smoke_module()

    with pytest.raises(RuntimeError, match="found 0"):
        smoke._find_one_wheel(tmp_path)

    first = tmp_path / "first.whl"
    second = tmp_path / "second.whl"
    first.touch()
    assert smoke._find_one_wheel(tmp_path) == first.resolve()

    second.touch()
    with pytest.raises(RuntimeError, match="found 2"):
        smoke._find_one_wheel(tmp_path)


def test_import_prefix_check_does_not_use_fragile_string_prefixes(tmp_path):
    smoke = _load_smoke_module()
    prefix = tmp_path / "venv"
    package = prefix / "Lib" / "site-packages" / "qzx" / "__init__.py"
    lookalike = tmp_path / "venv-shadow" / "qzx" / "__init__.py"

    assert smoke._is_within(package, prefix) is True
    assert smoke._is_within(lookalike, prefix) is False


def test_missing_wheel_failure_is_machine_readable(tmp_path, capsys):
    smoke = _load_smoke_module()

    exit_code = smoke.main(["--dist-dir", str(tmp_path)])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert payload["success"] is False
    assert payload["error_type"] == "RuntimeError"
    assert "found 0" in payload["error"]


def test_ci_runs_installed_smoke_after_artifact_verification():
    lines = WORKFLOW_PATH.read_text(encoding="utf-8").splitlines()
    verifier_indexes = [
        index
        for index, line in enumerate(lines)
        if "verify_distribution_artifacts.py" in line
    ]
    smoke_indexes = [
        index
        for index, line in enumerate(lines)
        if "smoke_installed_distribution.py" in line
    ]

    assert len(verifier_indexes) == 1
    assert len(smoke_indexes) == 1
    assert verifier_indexes[0] < smoke_indexes[0]
    smoke_block = "\n".join(lines[smoke_indexes[0] - 2 : smoke_indexes[0] + 3])
    assert "Exercise the installed wheel outside the checkout" in smoke_block
    assert '--dist-dir "$RUNNER_TEMP/qzx-dist"' in smoke_block


def test_utf16_fixture_uses_byte_exact_newlines():
    source = SCRIPT_PATH.read_text(encoding="utf-8")

    assert '"one\\r\\ntwo\\n".encode("utf-16")' in source
    assert '.write_text(\n            "one\\r\\ntwo\\n"' not in source
