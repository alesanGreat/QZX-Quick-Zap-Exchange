"""Execution workflow for runScript."""

from __future__ import annotations

import os
import subprocess


def execute_script(command, capture_factory, script_path, args):
    """Execute one reviewed script through the command's compatibility hooks."""
    absolute_script, failure = _validated_script_path(command, script_path)
    if failure is not None:
        return failure

    command_line, script_type, failure = _script_command(
        command,
        absolute_script,
        args,
    )
    if failure is not None:
        return failure

    script_info, failure = _script_metadata(
        command,
        absolute_script,
        script_type,
        len(args),
    )
    if failure is not None:
        return failure

    process, failure = _start_process(
        command,
        command_line,
        absolute_script,
        script_type,
    )
    if failure is not None:
        return failure

    return _wait_for_script(
        command,
        capture_factory,
        process,
        absolute_script,
        script_type,
        script_info,
    )


def _validated_script_path(command, script_path):
    try:
        absolute_script = os.path.abspath(os.fspath(script_path))
    except TypeError:
        return None, command._failure(
            "invalid_script_path",
            "script_path must be a filesystem path.",
            script_path=str(script_path),
        )
    if not os.path.exists(absolute_script):
        return None, command._failure(
            "script_not_found",
            f"Script does not exist: {absolute_script}",
            script_path=absolute_script,
        )
    if not os.path.isfile(absolute_script):
        return None, command._failure(
            "script_not_regular_file",
            f"Script path is not a regular file: {absolute_script}",
            script_path=absolute_script,
        )
    return absolute_script, None


def _script_command(command, absolute_script, args):
    try:
        command_line, script_type = command._command_for_script(
            absolute_script,
            args,
        )
        return command_line, script_type, None
    except ValueError as exc:
        return None, None, command._failure(
            "unsupported_script_type",
            str(exc),
            script_path=absolute_script,
        )


def _script_metadata(command, absolute_script, script_type, argument_count):
    try:
        info = command._script_info(
            absolute_script,
            script_type,
            argument_count,
        )
        return info, None
    except OSError as exc:
        return None, command._failure(
            "script_metadata_unavailable",
            f"Could not inspect the {script_type} script before execution: {exc}",
            script_path=absolute_script,
            script_type=script_type,
        )


def _start_process(command, command_line, absolute_script, script_type):
    try:
        process = subprocess.Popen(
            command_line,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
            **command._process_group_options(),
        )
        return process, None
    except OSError as exc:
        return None, command._failure(
            "script_start_failed",
            f"Could not start the {script_type} script: {exc}",
            script_path=absolute_script,
            script_type=script_type,
        )


def _wait_for_script(
    command,
    capture_factory,
    process,
    absolute_script,
    script_type,
    script_info,
):
    assert process.stdout is not None
    assert process.stderr is not None
    stdout_capture = capture_factory(
        process.stdout,
        command.retained_output_bytes,
    )
    stderr_capture = capture_factory(
        process.stderr,
        command.retained_output_bytes,
    )
    stdout_capture.start()
    stderr_capture.start()

    try:
        exit_code = process.wait(timeout=command.timeout_seconds)
    except subprocess.TimeoutExpired:
        return _timeout_result(
            command,
            process,
            absolute_script,
            script_type,
            script_info,
            stdout_capture,
            stderr_capture,
        )
    return _completed_result(
        command,
        exit_code,
        absolute_script,
        script_type,
        script_info,
        stdout_capture,
        stderr_capture,
    )


def _timeout_result(
    command,
    process,
    absolute_script,
    script_type,
    script_info,
    stdout_capture,
    stderr_capture,
):
    termination = command._terminate_process_tree(process)
    stdout = stdout_capture.finish()
    stderr = stderr_capture.finish()
    return {
        "success": False,
        "message": (
            f"{script_type} script '{os.path.basename(absolute_script)}' "
            f"exceeded the {command.timeout_seconds}-second timeout."
        ),
        "error": "Script execution timed out.",
        "error_code": "script_timeout",
        "script": script_info,
        "execution": {
            "timeout_seconds": command.timeout_seconds,
            "exit_code": None,
            "timed_out": True,
            "termination": termination,
        },
        "stdout": stdout,
        "stderr": stderr,
    }


def _completed_result(
    command,
    exit_code,
    absolute_script,
    script_type,
    script_info,
    stdout_capture,
    stderr_capture,
):
    stdout = stdout_capture.finish()
    stderr = stderr_capture.finish()
    success = exit_code == 0
    message = _completion_message(
        success,
        exit_code,
        absolute_script,
        script_type,
    )
    result = {
        "success": success,
        "message": message,
        "script": script_info,
        "execution": {
            "timeout_seconds": command.timeout_seconds,
            "exit_code": exit_code,
            "timed_out": False,
        },
        "stdout": stdout,
        "stderr": stderr,
    }
    if not success:
        result["error"] = "Script returned a non-zero exit code."
        result["error_code"] = "script_failed"
    return result


def _completion_message(success, exit_code, absolute_script, script_type):
    name = os.path.basename(absolute_script)
    if success:
        return f"Executed {script_type} script '{name}' successfully."
    return f"{script_type} script '{name}' exited with code {exit_code}."
