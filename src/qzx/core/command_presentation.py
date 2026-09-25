"""Shared help and result normalization for QZX commands."""

from __future__ import annotations

import re


def build_command_help(command):
    """Return the complete public help text for one command."""
    maturity = command.get_maturity()
    lines = [
        f"Command: {command.name}",
        f"Description: {command.description}",
        f"Maturity: {maturity['label']}",
        f"  {maturity['summary']}",
        "",
    ]
    _append_parameter_help(lines, command.parameters)
    _append_example_help(lines, command.examples)
    _append_safety_help(lines, command)
    return "\n".join(lines)


def _append_parameter_help(lines, parameters):
    if not parameters:
        return
    lines.append("Parameters:")
    for parameter in parameters:
        name = parameter.get("name", "unknown")
        description = parameter.get("description", "")
        required_text = "Required" if parameter.get("required", False) else "Optional"
        default = parameter.get("default")
        default_text = f" (Default: {default})" if default is not None else ""
        lines.append(f"  - {name}: {description} [{required_text}{default_text}]")
    lines.append("")


def _append_example_help(lines, examples):
    if not examples:
        return
    lines.append("Examples:")
    for example in examples:
        lines.append(f"  {example.get('command', '')}")
        description = example.get("description", "")
        if description:
            lines.append(f"    {description}")
    lines.append("")


def _append_safety_help(lines, command):
    if not command.requires_explicit_approval:
        return
    if command.backup_target_parameter:
        lines.extend([
            "High-risk safety:",
            "  Preview or validation modes do not create a backup.",
            "  Mutations create a safety backup before execution by default.",
            "  --dangerously-bypass-approvals-and-sandbox (alias: --yolo) skips it.",
            "  QZX_SAFETY=YOLO also skips it for all high-risk commands.",
            "  Configure it with QZX_BACKUPS_PATH, QZX_BACKUPS_FORMAT,",
            "  and QZX_BACKUPS_COMPRESSION.",
            "",
        ])
        return
    lines.extend([
        "High-risk safety:",
        "  This operation has no restorable filesystem backup target.",
        "  Execution requires --dangerously-bypass-approvals-and-sandbox",
        "  its alias --yolo, or QZX_SAFETY=YOLO.",
        "",
    ])


def format_command_result(command, result):
    """Normalize one command result to the shared structured envelope."""
    if isinstance(result, dict):
        return _format_mapping_result(command, result)
    return _format_legacy_result(result)


def _format_mapping_result(command, result):
    formatted = dict(result)
    if "success" not in formatted:
        formatted["success"] = _infer_success(formatted)
    formatted["success"] = bool(formatted["success"])
    if not formatted.get("message"):
        formatted["message"] = _default_message(command, formatted)
    formatted["message"] = str(formatted["message"])
    if not formatted["success"] and not formatted.get("error"):
        formatted["error"] = formatted["message"]
    return formatted


def _infer_success(result):
    status = str(result.get("status", "")).strip().lower()
    if status in {"success", "ok", "passed"}:
        return True
    if status in {"error", "failed", "failure"}:
        return False
    return not bool(result.get("error"))


def _default_message(command, result):
    if result.get("error"):
        return str(result["error"])
    if result["success"]:
        return "Command {} executed successfully.".format(command.name)
    return "Command {} failed.".format(command.name)


def _format_legacy_result(result):
    message = str(result)
    looks_like_error = bool(
        re.match(
            r"^\s*(?:error|failed|failure|exception)\b",
            message,
            flags=re.IGNORECASE,
        )
    )
    formatted = {
        "success": not looks_like_error,
        "result": result,
        "message": message,
    }
    if looks_like_error:
        formatted["error"] = message
        formatted["error_code"] = "legacy_unstructured_error"
    else:
        formatted["warnings"] = ["Command returned a legacy unstructured value."]
    return formatted
