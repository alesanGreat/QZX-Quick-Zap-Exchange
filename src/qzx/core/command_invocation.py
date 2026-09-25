"""Fail-closed orchestration for one public QZX command invocation."""

from __future__ import annotations


def invoke_command(command, args, *, clock, environ):
    """Parse, protect, execute, and normalize one command invocation."""
    start = clock()
    valid, values, error = command.parse_arguments(args or [])
    if not valid:
        return command._finalize_invocation_result(error, start)
    safety_backup, safety_error, failed_backup = _prepare_safety(
        command, values, environ
    )
    if safety_error is not None:
        return command._finalize_invocation_result(
            safety_error, start, safety_backup=failed_backup
        )
    raw_result = _execute_command(command, values)
    return command._finalize_invocation_result(
        raw_result, start, safety_backup=safety_backup
    )


def _prepare_safety(command, values, environ):
    flag_bypass = values.pop("__qzx_approval_granted", False)
    environment_bypass = environ.get("QZX_SAFETY", "").strip().upper() == "YOLO"
    bypass_requested = flag_bypass or environment_bypass
    if not command.requires_explicit_approval:
        return None, None, None
    parameter_names = {parameter.get("name") for parameter in command.parameters}
    if bypass_requested:
        _apply_bypass_values(values, parameter_names)
    if not command._requested_high_risk_mutation(values):
        return None, None, None
    if bypass_requested:
        reason = "explicit_bypass_flag" if flag_bypass else "QZX_SAFETY=YOLO"
        return _bypassed_backup(command, reason), None, None
    return _create_required_backup(command, values)


def _apply_bypass_values(values, parameter_names):
    if "apply" in parameter_names:
        values["apply"] = True
    if "dry_run" in parameter_names:
        values["dry_run"] = False


def _bypassed_backup(command, reason):
    return {
        "status": "bypassed",
        "reason": reason,
        "command": command.name,
    }


def _create_required_backup(command, values):
    target = command.get_safety_backup_target(values)
    if target is None:
        return None, _missing_backup_target(command), None
    preflight_failure = command.validate_safety_backup_target(target, values)
    if preflight_failure is not None:
        return None, preflight_failure, None
    try:
        from qzx.core.safety_backup import create_safety_backup

        return create_safety_backup(command.name, target), None, None
    except Exception as exc:
        failed = {"status": "failed", "target": str(target)}
        return None, _backup_failure(command, target, exc), failed


def _missing_backup_target(command):
    return {
        "success": False,
        "error_code": "approval_required",
        "error": "This high-risk operation has no restorable filesystem backup target.",
        "message": (
            "Review the operation, then add "
            "--dangerously-bypass-approvals-and-sandbox "
            "(or --yolo) to execute it."
        ),
        "details": {
            "command": command.name,
            "bypass_flags": sorted(command.approval_flags),
        },
    }


def _backup_failure(command, target, exc):
    return {
        "success": False,
        "error_code": "safety_backup_failed",
        "error": "{}: {}".format(type(exc).__name__, str(exc)),
        "message": (
            "Command '{}' was not executed because its required "
            "safety backup could not be created: {}"
        ).format(command.name, str(exc)),
        "details": {
            "command": command.name,
            "backup_target": str(target),
            "bypass_flags": sorted(command.approval_flags),
        },
    }


def _execute_command(command, values):
    try:
        return _call_execute(command, values)
    except Exception as exc:
        return {
            "success": False,
            "error": "{}: {}".format(type(exc).__name__, str(exc)),
            "error_code": "command_execution_error",
            "message": "Command '{}' failed: {}".format(command.name, str(exc)),
        }


def _call_execute(command, values):
    variadic = next(
        (parameter for parameter in command.parameters if parameter.get("is_variadic")),
        None,
    )
    if variadic is None or not _execute_accepts_varargs(command):
        return command.execute(**values)
    variadic_name = variadic["name"]
    variadic_values = values.get(variadic_name, [])
    positional_values = [
        values[parameter["name"]]
        for parameter in command.parameters
        if not parameter.get("is_variadic") and parameter.get("name") in values
    ]
    return command.execute(*positional_values, *variadic_values)


def _execute_accepts_varargs(command):
    import inspect

    signature = inspect.signature(command.execute)
    return any(
        parameter.kind == inspect.Parameter.VAR_POSITIONAL
        for parameter in signature.parameters.values()
    )
