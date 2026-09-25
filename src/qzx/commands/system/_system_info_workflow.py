"""Workflow and presentation for getSystemInfo."""

from __future__ import annotations


def _invalid_boolean(detailed, include_environment, error):
    return {
        "success": False,
        "error_code": "invalid_boolean",
        "error": str(error),
        "message": (
            "The detailed and include_environment values must each be true or false."
        ),
        "details": {
            "detailed": detailed,
            "include_environment": include_environment,
        },
    }


def _collection_failure(detailed, include_environment, error):
    return {
        "success": False,
        "error_code": "system_info_unavailable",
        "error": f"{type(error).__name__}: {error}",
        "message": (
            "QZX could not collect the portable system summary. Verify that "
            "the current directory and operating-system account information "
            "are accessible, then retry."
        ),
        "details": {
            "detailed_requested": detailed,
            "environment_requested": include_environment,
        },
    }


def execute_system_info(command, detailed=False, include_environment=False):
    """Run the public getSystemInfo workflow."""
    try:
        detailed_value = command._normalize_bool(detailed)
        environment_value = command._normalize_bool(include_environment)
    except ValueError as exc:
        return _invalid_boolean(detailed, include_environment, exc)
    try:
        info = command._collect_core_info(environment_value)
    except (OSError, RuntimeError, ValueError) as exc:
        return _collection_failure(detailed_value, environment_value, exc)
    warnings = []
    if detailed_value:
        details, detail_warnings = command._details_collector()
        info.update(details)
        warnings.extend(detail_warnings)
    message = command._build_message(
        info,
        detailed=detailed_value,
        include_environment=environment_value,
        warnings=warnings,
    )
    return {
        "success": True,
        "message": message,
        "system_info": info,
        "details_requested": detailed_value,
        "environment_included": environment_value,
        "warnings": warnings,
    }


def _detail_message(info):
    available = [
        label
        for field, label in (("memory", "RAM"), ("storage", "storage"))
        if field in info
    ]
    return (
        " Detailed sections: {}. GPU discovery stays opt-in through "
        "'qzx getGpuInfo' because it may invoke native vendor tools."
    ).format(", ".join(available) if available else "none available")


def _environment_message(info, include_environment):
    if include_environment:
        count = len(info["environment"].get("environment_variables", {}))
        return f" Included {count} selected environment variables."
    return (
        " Environment-variable values were not included; add "
        "--include-environment to request them locally."
    )


def build_system_info_message(info, *, detailed, include_environment, warnings):
    """Build the human-readable summary without changing structured data."""
    python_info = info["python"]
    message = (
        "System: {} {} on {} ({}-bit). Python {} {}. "
        "Host: {}; user: {}; current directory: {}."
    ).format(
        info["os"],
        info["os_release"],
        info["machine"] or "unknown architecture",
        info["architecture"]["bits"],
        python_info["implementation"],
        python_info["version"],
        info["network"]["hostname"],
        info["user"]["username"],
        info["environment"]["current_directory"],
    )
    if detailed:
        message += _detail_message(info)
    else:
        message += " Add --detailed for RAM and storage without probing GPUs."
    message += _environment_message(info, include_environment)
    if warnings:
        message += " Partial-data warnings: {}.".format(len(warnings))
    return message
