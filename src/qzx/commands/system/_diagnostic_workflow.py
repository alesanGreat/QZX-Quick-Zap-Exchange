"""Execution workflow for runDiagnosticCommand."""

from __future__ import annotations

import datetime
import os


def execute_diagnostic(command, process_runner, native_command, args):
    """Validate and run one trusted read-only native diagnostic."""
    request = _request_state(command, native_command, args)
    failure = _request_failure(command, request)
    if failure is not None:
        return failure

    executable = command._trusted_executable(
        request["name"],
        request["platform_family"],
    )
    if executable is None:
        return command._failure(
            "trusted_executable_not_found",
            "No trusted system copy of '{}' was found.".format(
                request["name"]
            ),
            (
                "Install the operating-system diagnostic in a standard system "
                "directory; QZX does not execute PATH or current-directory "
                "substitutes."
            ),
            request["details"],
        )

    _complete_command_details(command, request, executable)
    execution, failure = _run_execution(
        command,
        process_runner,
        request,
        executable,
    )
    if failure is not None:
        return failure

    execution_details = _execution_details(
        request["details"],
        execution,
    )
    return _execution_result(
        command,
        request["name"],
        execution,
        execution_details,
    )


def _request_state(command, native_command, args):
    command_name = str(native_command).strip().lower()
    argument_list = [str(value) for value in args]
    system_name = "windows" if os.name == "nt" else "unix"
    available = (
        command._WINDOWS_COMMANDS
        if system_name == "windows"
        else command._UNIX_COMMANDS
    )
    return {
        "name": command_name,
        "args": argument_list,
        "platform_family": system_name,
        "available": available,
        "details": {
            "name": command_name,
            "args": argument_list,
            "platform_family": system_name,
            "shell": False,
            "timeout_seconds": command.TIMEOUT_SECONDS,
            "stdout_limit_bytes": command.STDOUT_LIMIT_BYTES,
            "stderr_limit_bytes": command.STDERR_LIMIT_BYTES,
        },
    }


def _request_failure(command, request):
    name = request["name"]
    if (
        not name
        or name != os.path.basename(name)
        or "/" in name
        or "\\" in name
        or "\x00" in name
    ):
        return command._failure(
            "invalid_command_name",
            "A diagnostic command must be one bare executable name.",
            "Choose a name from the platform-specific allowlist.",
            request["details"],
            allowed_commands=sorted(request["available"]),
        )
    if name not in request["available"]:
        return _not_allowlisted(command, request)

    argument_error = command._validate_arguments(
        name,
        request["args"],
        request["platform_family"],
    )
    if argument_error is None:
        return None
    return command._failure(
        "arguments_not_allowlisted",
        argument_error,
        (
            "Use only the documented read-only form, or run the native utility "
            "directly after reviewing its effects."
        ),
        request["details"],
    )


def _not_allowlisted(command, request):
    return command._failure(
        "command_not_allowlisted",
        "Command '{}' is outside the read-only diagnostic allowlist.".format(
            request["name"]
        ),
        (
            "Use a dedicated QZX command. Network checks belong to checkDns, "
            "checkUrlStatus, or getNetworkConfig; paths and files belong to the "
            "dedicated file commands; processes and sessions belong to "
            "listProcesses or getCurrentUser."
        ),
        request["details"],
        allowed_commands=sorted(request["available"]),
    )


def _complete_command_details(command, request, executable):
    details = request["details"]
    details["executable"] = executable
    details["working_directory"] = os.path.dirname(executable)
    details["environment_policy"] = "minimal_trusted"
    details["started_at"] = datetime.datetime.now(
        datetime.timezone.utc
    ).isoformat()


def _run_execution(command, process_runner, request, executable):
    try:
        execution = process_runner(
            [executable, *request["args"]],
            timeout_seconds=command.TIMEOUT_SECONDS,
            stdout_limit=command.STDOUT_LIMIT_BYTES,
            stderr_limit=command.STDERR_LIMIT_BYTES,
            cwd=request["details"]["working_directory"],
            env=command._diagnostic_environment(
                executable,
                request["platform_family"],
            ),
        )
        return execution, None
    except OSError as exc:
        return None, command._failure(
            "command_execution_failed",
            "{}: {}".format(type(exc).__name__, exc),
            "Verify the trusted system executable and retry.",
            request["details"],
        )


def _execution_details(command_details, execution):
    details = {
        "command": command_details,
        "exit_code": execution["return_code"],
        "duration_seconds": execution["duration_seconds"],
        "output": {
            "stdout_observed_bytes": execution["stdout_observed_bytes"],
            "stderr_observed_bytes": execution["stderr_observed_bytes"],
            "stdout_retained_bytes": execution["stdout_retained_bytes"],
            "stderr_retained_bytes": execution["stderr_retained_bytes"],
            "stdout_truncated": execution["stdout_truncated"],
            "stderr_truncated": execution["stderr_truncated"],
        },
    }
    if execution["reader_errors"]:
        details["reader_errors"] = execution["reader_errors"]
    return details


def _execution_result(command, name, execution, details):
    if execution["timed_out"]:
        return _timeout_result(command, name, execution, details)
    if execution["reader_errors"]:
        return _capture_failure(execution, details)
    return _completed_result(name, execution, details)


def _timeout_result(command, name, execution, details):
    return {
        "success": False,
        "error_code": "command_timeout",
        "error": (
            "Diagnostic command exceeded {} seconds.".format(
                command.TIMEOUT_SECONDS
            )
        ),
        "message": (
            "QZX terminated '{}' after its bounded diagnostic window. "
            "Narrow the requested view and retry."
        ).format(name),
        "stdout": execution["stdout"],
        "stderr": execution["stderr"],
        "details": details,
    }


def _capture_failure(execution, details):
    return {
        "success": False,
        "error_code": "output_capture_failed",
        "error": "; ".join(execution["reader_errors"]),
        "message": (
            "The read-only diagnostic finished, but QZX could not capture its "
            "complete bounded output. Treat the result as incomplete and retry."
        ),
        "stdout": execution["stdout"],
        "stderr": execution["stderr"],
        "details": details,
    }


def _completed_result(name, execution, details):
    success = execution["return_code"] == 0
    return {
        "success": success,
        "message": _completion_message(name, execution, success),
        "error": (
            None
            if success
            else execution["stderr"].strip()
            or "The native diagnostic returned a non-zero exit status."
        ),
        "stdout": execution["stdout"],
        "stderr": execution["stderr"],
        "details": details,
    }


def _completion_message(name, execution, success):
    if success:
        return (
            "Read-only diagnostic '{}' completed successfully in {:.3f} "
            "seconds; {} stdout bytes and {} stderr bytes were observed."
        ).format(
            name,
            execution["duration_seconds"],
            execution["stdout_observed_bytes"],
            execution["stderr_observed_bytes"],
        )
    return (
        "Read-only diagnostic '{}' exited with code {} after {:.3f} seconds. "
        "Review stderr and verify that its options are supported on this "
        "operating system."
    ).format(
        name,
        execution["return_code"],
        execution["duration_seconds"],
    )
