"""Validated termination workflow for killProcess."""

from __future__ import annotations

import platform


def execute_kill_process(
    command,
    pid,
    force=False,
    expected_create_time=None,
    wait_seconds=5.0,
):
    """Terminate one validated process and verify observable exit."""
    request, failure = _normalize_request(
        command,
        pid,
        force,
        expected_create_time,
        wait_seconds,
    )
    if failure is not None:
        return failure
    context, failure = _termination_context(command, request)
    if failure is not None:
        return failure
    return _terminate_and_wait(
        command,
        context["psutil"],
        context["process"],
        request,
        context["name"],
        context["details"],
    )


def _termination_context(command, request):
    psutil, failure = _load_psutil(command, request["pid"])
    if failure is not None:
        return None, failure
    inspected, failure = _inspect_process(command, psutil, request["pid"])
    if failure is not None:
        return None, failure

    process = inspected["process"]
    protected = command._protected_reason(process, inspected["name"], psutil)
    if protected is not None:
        return None, command._failure(
            "protected_process",
            protected,
            pid=request["pid"],
            name=inspected["name"],
            create_time=inspected["create_time"],
        )
    failure = _identity_failure(command, request, inspected)
    if failure is not None:
        return None, failure
    details = command._process_details(
        process,
        inspected["name"],
        inspected["create_time"],
        request["force"],
        platform.system(),
        psutil,
    )
    return {
        "psutil": psutil,
        "process": process,
        "name": inspected["name"],
        "details": details,
    }, None


def _normalize_request(
    command,
    pid,
    force,
    expected_create_time,
    wait_seconds,
):
    parsed_pid, failure = _positive_pid(command, pid)
    if failure is not None:
        return None, failure
    force_value = command._parse_bool(force)
    if force_value is None:
        return None, command._failure(
            "invalid_force",
            f"force must be true or false, got {force!r}.",
            pid=parsed_pid,
        )
    wait_value, failure = _wait_value(command, parsed_pid, wait_seconds)
    if failure is not None:
        return None, failure
    expected_time, failure = _expected_time(
        command,
        parsed_pid,
        expected_create_time,
    )
    if failure is not None:
        return None, failure
    return {
        "pid": parsed_pid,
        "force": force_value,
        "wait_seconds": wait_value,
        "expected_create_time": expected_time,
    }, None


def _positive_pid(command, pid):
    try:
        parsed_pid = int(pid)
    except (TypeError, ValueError):
        return None, command._failure(
            "invalid_pid",
            f"PID must be a positive integer, got {pid!r}.",
            pid=pid,
        )
    if parsed_pid > 0:
        return parsed_pid, None
    return None, command._failure(
        "invalid_pid",
        f"PID must be a positive integer, got {parsed_pid}.",
        pid=parsed_pid,
    )


def _wait_value(command, pid, wait_seconds):
    try:
        wait_value = float(wait_seconds)
    except (TypeError, ValueError):
        return None, command._failure(
            "invalid_wait_seconds",
            (
                "wait_seconds must be a number from 0.1 to 60, "
                f"got {wait_seconds!r}."
            ),
            pid=pid,
        )
    if 0.1 <= wait_value <= 60:
        return wait_value, None
    return None, command._failure(
        "invalid_wait_seconds",
        f"wait_seconds must be from 0.1 to 60, got {wait_value}.",
        pid=pid,
    )


def _expected_time(command, pid, expected_create_time):
    if expected_create_time in (None, ""):
        return None, None
    try:
        expected_time = float(expected_create_time)
    except (TypeError, ValueError):
        return None, command._failure(
            "invalid_expected_create_time",
            (
                "expected_create_time must be a positive timestamp, "
                f"got {expected_create_time!r}."
            ),
            pid=pid,
        )
    if expected_time > 0:
        return expected_time, None
    return None, command._failure(
        "invalid_expected_create_time",
        "expected_create_time must be a positive timestamp.",
        pid=pid,
    )


def _load_psutil(command, pid):
    try:
        import psutil
    except ImportError:
        return None, command._failure(
            "missing_dependency",
            (
                "killProcess requires psutil. Install QZX with its normal "
                "runtime dependencies before retrying."
            ),
            pid=pid,
        )
    return psutil, None


def _inspect_process(command, psutil, pid):
    try:
        process = psutil.Process(pid)
        return {
            "process": process,
            "create_time": process.create_time(),
            "name": process.name(),
        }, None
    except psutil.NoSuchProcess:
        return None, command._failure(
            "process_not_found",
            f"Process PID {pid} does not exist or already exited.",
            pid=pid,
        )
    except psutil.AccessDenied:
        return None, command._failure(
            "process_inspection_denied",
            (
                f"QZX could not inspect PID {pid}. Run with the "
                "operating-system privileges required for that process."
            ),
            pid=pid,
        )


def _identity_failure(command, request, inspected):
    expected = request["expected_create_time"]
    observed = inspected["create_time"]
    if expected is None or abs(observed - expected) <= 0.001:
        return None
    return command._failure(
        "process_identity_changed",
        (
            f"PID {request['pid']} now has creation time {observed}, "
            f"not the expected {expected}. No signal was sent."
        ),
        pid=request["pid"],
        name=inspected["name"],
        expected_create_time=expected,
        observed_create_time=observed,
    )


def _terminate_and_wait(
    command,
    psutil,
    process,
    request,
    process_name,
    process_details,
):
    method = "kill" if request["force"] else "terminate"
    try:
        if request["force"]:
            process.kill()
        else:
            process.terminate()
        exit_code = process.wait(timeout=request["wait_seconds"])
    except psutil.NoSuchProcess:
        exit_code = None
    except psutil.TimeoutExpired:
        return _timeout_result(request, process_details, method)
    except psutil.AccessDenied:
        return command._failure(
            "termination_denied",
            (
                f"Access was denied while terminating PID {request['pid']}. "
                "Use the operating-system privileges required for that process."
            ),
            **process_details,
        )
    except Exception as exc:
        return command._failure(
            "termination_failed",
            (
                f"Could not terminate PID {request['pid']}: "
                f"{type(exc).__name__}: {exc}"
            ),
            **process_details,
        )
    return _success_result(
        request,
        process_name,
        process_details,
        method,
        exit_code,
    )


def _timeout_result(request, process_details, method):
    wait_value = request["wait_seconds"]
    return {
        "success": False,
        "error_code": "process_still_running",
        "error": (
            f"PID {request['pid']} did not exit within "
            f"{wait_value:.3g} seconds."
        ),
        "message": (
            f"QZX sent {method} to PID {request['pid']}, but could not verify "
            f"exit within {wait_value:.3g} seconds. Inspect it again before "
            "deciding whether to force termination."
        ),
        "process": process_details,
        "termination": {
            "requested_method": method,
            "wait_seconds": wait_value,
            "verified_exited": False,
        },
    }


def _success_result(
    request,
    process_name,
    process_details,
    method,
    exit_code,
):
    return {
        "success": True,
        "status": "terminated",
        "process": process_details,
        "termination": {
            "method": method,
            "wait_seconds": request["wait_seconds"],
            "verified_exited": True,
            "exit_code": exit_code,
        },
        "message": (
            f"Process {request['pid']} ({process_name}) was terminated with "
            f"{method}; QZX verified that it exited."
        ),
    }
