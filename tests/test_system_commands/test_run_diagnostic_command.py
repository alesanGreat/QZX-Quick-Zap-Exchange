#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Real-process and policy tests for the native diagnostic boundary."""

import os
import pathlib
import sys

from qzx.commands.system.run_diagnostic_command import (
    _BoundedStreamCapture,
    RunDiagnosticCommand,
    _run_bounded_process,
    _subprocess_output_encoding,
)


def test_real_whoami_uses_a_trusted_system_executable():
    result = RunDiagnosticCommand().execute("whoami")

    assert result["success"] is True, result
    assert result["stdout"].strip()
    assert result["stderr"] == ""
    assert result["details"]["exit_code"] == 0
    assert (
        result["details"]["command"]["environment_policy"]
        == "minimal_trusted"
    )
    executable = pathlib.Path(
        result["details"]["command"]["executable"]
    ).resolve()
    if os.name == "nt":
        trusted_directory = pathlib.Path(
            RunDiagnosticCommand._windows_system_directory()
        ).resolve()
        assert executable.parent == trusted_directory
    else:
        trusted_directories = {
            pathlib.Path(directory).resolve()
            for directory in RunDiagnosticCommand._TRUSTED_UNIX_DIRECTORIES
            if pathlib.Path(directory).is_dir()
        }
        assert executable.parent in trusted_directories


def test_declared_result_schema_covers_success_and_failure_shapes():
    properties = RunDiagnosticCommand.result_schema["properties"]
    error_types = {
        alternative["type"]
        for alternative in properties["error"]["oneOf"]
    }

    assert properties["success"] == {"type": "boolean"}
    assert properties["message"] == {"type": "string"}
    assert properties["stdout"] == {"type": "string"}
    assert properties["stderr"] == {"type": "string"}
    assert properties["details"]["type"] == "object"
    assert error_types == {"null", "string"}


def test_windows_executable_resolution_ignores_a_forged_systemroot(
    monkeypatch,
    tmp_path,
):
    forged_directory = tmp_path / "System32"
    forged_directory.mkdir()
    forged_executable = forged_directory / "whoami.exe"
    forged_executable.write_bytes(b"not a Windows executable")
    monkeypatch.setenv("SystemRoot", str(tmp_path))

    if os.name != "nt":
        assert RunDiagnosticCommand._windows_system_directory() is None
        assert RunDiagnosticCommand._trusted_executable(
            "whoami",
            "windows",
        ) is None
        return

    executable = RunDiagnosticCommand._trusted_executable(
        "whoami",
        "windows",
    )

    assert executable is not None
    assert pathlib.Path(executable).resolve() != forged_executable.resolve()
    assert pathlib.Path(executable).parent.resolve() == pathlib.Path(
        RunDiagnosticCommand._windows_system_directory()
    ).resolve()


def test_network_and_mutating_utilities_are_not_allowlisted():
    command = RunDiagnosticCommand()

    for native_name in (
        "df",
        "ip",
        "ifconfig",
        "ping",
        "printenv",
        "ps",
        "systeminfo",
        "tasklist",
        "where",
        "which",
        "who",
    ):
        result = command.execute(native_name)
        assert result["success"] is False
        assert result["error_code"] == "command_not_allowlisted"
        assert "dedicated QZX command" in result["message"]


def test_argument_grammars_reject_known_mutating_forms():
    assert RunDiagnosticCommand._validate_windows_arguments(
        "ipconfig",
        ["/flushdns"],
    )
    assert RunDiagnosticCommand._validate_unix_arguments(
        "ss",
        ["-K"],
    )
    assert RunDiagnosticCommand._validate_unix_arguments(
        "ss",
        ["--kill"],
    )
    assert RunDiagnosticCommand._validate_unix_arguments(
        "ss",
        ["-p"],
    )
    assert RunDiagnosticCommand._validate_unix_arguments(
        "ss",
        [],
    )
    assert RunDiagnosticCommand._validate_unix_arguments(
        "ss",
        ["-x"],
    )
    assert RunDiagnosticCommand._validate_unix_arguments(
        "netstat",
        ["-np"],
    )
    assert RunDiagnosticCommand._validate_windows_arguments(
        "netstat",
        ["-ano"],
    )
    assert RunDiagnosticCommand._validate_windows_arguments(
        "netstat",
        [],
    )
    assert RunDiagnosticCommand._validate_unix_arguments(
        "netstat",
        ["-a"],
    )
    assert RunDiagnosticCommand._validate_windows_arguments(
        "netstat",
        ["-an"],
    ) is None
    assert RunDiagnosticCommand._validate_unix_arguments(
        "netstat",
        ["-lnt"],
    ) is None
    assert RunDiagnosticCommand._validate_unix_arguments(
        "ss",
        ["-lnt"],
    ) is None


def test_diagnostic_environment_does_not_inherit_process_secrets(
    monkeypatch,
):
    monkeypatch.setenv("QZX_TEST_SECRET", "must-not-reach-child")
    system_name = "windows" if os.name == "nt" else "unix"
    executable = RunDiagnosticCommand._trusted_executable(
        "whoami",
        system_name,
    )

    environment = RunDiagnosticCommand._diagnostic_environment(
        executable,
        system_name,
    )

    assert "QZX_TEST_SECRET" not in environment
    assert environment["PATH"]
    assert set(environment).issubset(
        {
            "LANG",
            "LC_ALL",
            "LC_CTYPE",
            "PATH",
            "PATHEXT",
            "SystemRoot",
            "WINDIR",
        }
    )


def test_capture_bounds_each_stream_while_draining_the_real_process():
    result = _run_bounded_process(
        [
            sys.executable,
            "-c",
            (
                "import sys;"
                "sys.stdout.buffer.write(b'A' * 4096);"
                "sys.stderr.buffer.write(b'B' * 2048)"
            ),
        ],
        timeout_seconds=5,
        stdout_limit=128,
        stderr_limit=64,
    )

    assert result["return_code"] == 0
    assert result["timed_out"] is False
    assert result["stdout_observed_bytes"] == 4096
    assert result["stderr_observed_bytes"] == 2048
    assert result["stdout_retained_bytes"] == 128
    assert result["stderr_retained_bytes"] == 64
    assert result["stdout_truncated"] is True
    assert result["stderr_truncated"] is True
    assert result["stdout"].count("A") == 128
    assert result["stderr"].count("B") == 64
    assert result["reader_errors"] == []


def test_capture_decodes_native_non_ascii_output_without_replacement():
    sample = "Versión del sistema: Español - Bogotá"
    encoded = sample.encode(_subprocess_output_encoding())
    capture = _BoundedStreamCapture(1024)
    capture.chunks = [encoded]
    capture.observed_bytes = len(encoded)
    capture.retained_bytes = len(encoded)

    assert capture.text() == sample
    assert "\ufffd" not in capture.text()


def test_timeout_terminates_a_real_process():
    result = _run_bounded_process(
        [sys.executable, "-c", "import time; time.sleep(5)"],
        timeout_seconds=0.1,
        stdout_limit=128,
        stderr_limit=64,
    )

    assert result["timed_out"] is True
    assert result["return_code"] is not None
    assert result["duration_seconds"] < 3
