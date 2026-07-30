"""Tests for lookup-only and explicitly requested executable version probes."""

from pathlib import Path
from types import SimpleNamespace
import sys

from qzx.commands.system.check_executable import CheckExecutableCommand


def test_empty_executable_name():
    result = CheckExecutableCommand().execute("")

    assert result["success"] is False
    assert result["error_code"] == "invalid_executable"
    assert "cannot be empty" in result["error"]


def test_missing_executable_is_a_successful_negative_lookup():
    name = "qzx-tool-that-does-not-exist-8f3d7483"
    result = CheckExecutableCommand(path_lookup=lambda _: None).execute(name)

    assert result["success"] is True
    assert result["executable"] == name
    assert result["available"] is False
    assert result["version_checked"] is False


def test_default_lookup_never_executes_the_discovered_program(tmp_path):
    executable = tmp_path / "tool"
    executable.write_text("", encoding="utf-8")

    def unexpected_runner(*args, **kwargs):
        raise AssertionError("lookup-only mode must not execute the program")

    result = CheckExecutableCommand(
        path_lookup=lambda _: str(executable),
        runner=unexpected_runner,
    ).execute("tool")

    assert result["success"] is True
    assert result["available"] is True
    assert result["version_requested"] is False
    assert result["version_checked"] is False


def test_version_probe_uses_exact_path_one_safe_argument_and_bounded_options(
    tmp_path,
):
    executable = tmp_path / "tool"
    executable.write_text("", encoding="utf-8")
    observed = {}

    def fake_runner(argv, **kwargs):
        observed["argv"] = argv
        observed["kwargs"] = kwargs
        return SimpleNamespace(
            returncode=0,
            stdout="tool version 2.4.1\n",
            stderr="",
        )

    result = CheckExecutableCommand(
        path_lookup=lambda _: str(executable),
        runner=fake_runner,
    ).execute("tool", True)

    assert result["success"] is True
    assert result["version"] == "2.4.1"
    assert result["version_checked"] is True
    assert observed["argv"] == [str(executable.resolve()), "--version"]
    assert observed["kwargs"]["shell"] is False
    assert observed["kwargs"]["timeout"] == 3.0
    assert observed["kwargs"]["check"] is False


def test_invalid_version_boolean_fails_without_lookup_or_execution():
    def unexpected_lookup(_):
        raise AssertionError("invalid input must fail before PATH lookup")

    result = CheckExecutableCommand(path_lookup=unexpected_lookup).execute(
        "tool",
        "sometimes",
    )

    assert result["success"] is False
    assert result["error_code"] == "invalid_boolean"


def test_real_python_version_probe_is_opt_in():
    result = CheckExecutableCommand().execute(sys.executable, True)

    assert result["success"] is True
    assert result["available"] is True
    assert Path(result["executable_path"]) == Path(sys.executable).resolve()
    assert result["version_checked"] is True
    assert result["version"].lstrip("v").startswith("3.13")
