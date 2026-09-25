"""Human and strict-JSON rendering primitives for the QZX CLI."""

from __future__ import annotations

import re
from pathlib import Path


HUMAN_ACRONYMS = {
    "am": "AM", "api": "API", "cpu": "CPU", "dns": "DNS", "gpu": "GPU",
    "html": "HTML", "id": "ID", "ip": "IP", "json": "JSON", "mb": "MB",
    "mbps": "Mbps", "os": "OS", "pid": "PID", "pm": "PM", "qzx": "QZX",
    "ram": "RAM", "sha": "SHA", "ssl": "SSL", "url": "URL", "zip": "ZIP",
}
HUMAN_DISPLAY_FIELDS = ("output", "content", "report", "tree_text", "diff")
HUMAN_ALWAYS_VISIBLE_WITH_DISPLAY = {
    "error", "warning", "warnings", "next_steps", "recommendations",
}


def json_compatible(value):
    """Return a recursively strict JSON-compatible representation."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        import math

        return value if math.isfinite(value) else str(value)
    if isinstance(value, dict):
        return {str(key): json_compatible(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_compatible(item) for item in value]
    if isinstance(value, set):
        return [json_compatible(item) for item in sorted(value, key=lambda item: str(item))]
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            pass
    return str(value)


def human_label(name):
    """Turn a structured field name into a readable terminal label."""
    text = str(name)
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", text):
        return text
    words = text.replace("-", "_").split("_")
    formatted = [
        HUMAN_ACRONYMS.get(word.lower(), word[:1].upper() + word[1:])
        for word in words if word
    ]
    return " ".join(formatted) or "Value"


def human_scalar(value):
    """Format a scalar without leaking Python container representations."""
    if value is None:
        return "Not available"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return str(value)


def without_duplicate_text(value, displayed_text):
    """Remove exact text already used as the human presentation."""
    if isinstance(value, str):
        return None if value.strip() in displayed_text else value
    if isinstance(value, dict):
        cleaned = {
            key: without_duplicate_text(item, displayed_text)
            for key, item in value.items()
        }
        return {key: item for key, item in cleaned.items() if _has_content(item)}
    if isinstance(value, (list, tuple, set)):
        cleaned = [without_duplicate_text(item, displayed_text) for item in value]
        return [item for item in cleaned if _has_content(item)]
    return value


def _has_content(value):
    return value not in (None, "", [], {})


def append_human_value(lines, label, value, indent=0, *, labeler=human_label,
                       scalar=human_scalar):
    """Append a recursively formatted value to a terminal line buffer."""
    prefix = " " * indent
    if isinstance(value, dict):
        _append_mapping(lines, label, value, indent, labeler, scalar)
    elif isinstance(value, (list, tuple, set)):
        _append_sequence(lines, label, list(value), indent, labeler, scalar)
    elif isinstance(value, str) and "\n" in value:
        lines.append("{}{}:".format(prefix, label))
        lines.extend("{}  {}".format(prefix, line) for line in value.rstrip().splitlines())
    else:
        lines.append("{}{}: {}".format(prefix, label, scalar(value)))


def _append_mapping(lines, label, value, indent, labeler, scalar):
    if not value:
        return
    lines.append("{}{}:".format(" " * indent, label))
    for key, item in value.items():
        append_human_value(
            lines, labeler(key), item, indent + 2, labeler=labeler, scalar=scalar
        )


def _append_sequence(lines, label, items, indent, labeler, scalar):
    prefix = " " * indent
    if not items:
        lines.append("{}{}: None".format(prefix, label))
        return
    lines.append("{}{}:".format(prefix, label))
    for index, item in enumerate(items, 1):
        _append_sequence_item(lines, index, item, indent, labeler, scalar)


def _append_sequence_item(lines, index, item, indent, labeler, scalar):
    item_prefix = " " * (indent + 2)
    if isinstance(item, dict):
        lines.append("{}{}. Item".format(item_prefix, index))
        for key, nested in item.items():
            append_human_value(
                lines, labeler(key), nested, indent + 5,
                labeler=labeler, scalar=scalar,
            )
    elif isinstance(item, (list, tuple, set)):
        append_human_value(
            lines, "{}. Item".format(index), item, indent + 2,
            labeler=labeler, scalar=scalar,
        )
    else:
        lines.append("{}- {}".format(item_prefix, scalar(item)))


def visible_meta(result):
    """Expose meaningful operational metadata, not renderer internals."""
    meta = result.get("meta")
    if not isinstance(meta, dict):
        return None
    return {
        key: value for key, value in meta.items()
        if key not in {"command", "duration_ms", "schema_version"}
    }


def render_command_catalog(result, message):
    """Render listCommands from structured data without duplicating JSON."""
    categories = _catalog_categories(result)
    if categories is None:
        return None
    maturity_labels = _maturity_labels(categories)
    if maturity_labels is None:
        return None
    lines = message.splitlines()
    _append_maturity_summary(lines, result.get("maturity_summary"), maturity_labels)
    for category in sorted(categories, key=lambda value: str(value).lower()):
        _append_command_category(lines, category, categories[category])
    return "\n".join(lines).rstrip()


def _catalog_categories(result):
    meta = result.get("meta")
    categories = result.get("commands")
    if not isinstance(meta, dict) or meta.get("command") != "listCommands":
        return None
    return categories if isinstance(categories, dict) else None


def _maturity_labels(categories):
    labels = {}
    for commands in categories.values():
        if not isinstance(commands, list):
            return None
        for command in commands:
            maturity = command.get("maturity") if isinstance(command, dict) else None
            if not isinstance(maturity, dict):
                return None
            stage, label = maturity.get("stage"), maturity.get("label")
            if isinstance(stage, str) and isinstance(label, str):
                labels.setdefault(stage, label)
    return labels


def _append_maturity_summary(lines, summary, labels):
    if not isinstance(summary, dict) or not summary:
        return
    text = ", ".join(
        "{} {}".format(count, labels.get(stage, stage))
        for stage, count in summary.items()
    )
    lines.append("Maturity: {}".format(text))


def _append_command_category(lines, category, commands):
    if not commands:
        return
    lines.extend(["", "[{}]".format(str(category).upper())])
    for command in sorted(commands, key=lambda item: str(item.get("name", "")).lower()):
        maturity = command["maturity"]
        lines.append(
            "  {} [{}]: {}".format(
                command.get("name", "Unnamed command"),
                maturity.get("label", maturity.get("stage", "Unknown")),
                command.get("description", "No description available"),
            )
        )


def render_human(
    result, *, scalar=human_scalar, render_catalog=render_command_catalog,
    labeler=human_label, append_value=append_human_value,
    meta_filter=visible_meta, duplicate_filter=without_duplicate_text,
):
    """Render one structured result as warm, readable terminal text."""
    if not isinstance(result, dict):
        return scalar(result)
    message = _result_message(result)
    catalog = render_catalog(result, message)
    if catalog is not None:
        return catalog
    if len(message.splitlines()) >= 3:
        return message
    display_fields, displayed_text, presentation_keys = _display_fields(result, message)
    lines = [message]
    for key, value in display_fields:
        lines.extend(["", "{}:".format(labeler(key)), value])
    fields = _fields_to_render(
        result, display_fields, displayed_text, presentation_keys, duplicate_filter
    )
    meta = meta_filter(result)
    if meta:
        fields["meta"] = meta
    _append_details(lines, fields, labeler, append_value)
    return "\n".join(lines).rstrip()


def _result_message(result):
    message = str(result.get("message", "")).strip()
    if message:
        return message
    if result.get("success") is True:
        return "Command completed successfully."
    return "The command could not be completed."


def _display_fields(result, message):
    fields = []
    displayed_text = {message}
    presentation_keys = set()
    for key in HUMAN_DISPLAY_FIELDS:
        value = result.get(key)
        if isinstance(value, str) and value.strip():
            presentation_keys.add(key)
            if value.strip() not in message:
                fields.append((key, value.strip()))
                displayed_text.add(value.strip())
    for key, value in result.items():
        is_legacy_display = (
            key not in {"message", "error"}
            and key not in HUMAN_DISPLAY_FIELDS
            and isinstance(value, str)
            and len(value.strip().splitlines()) >= 3
        )
        if is_legacy_display:
            fields.append((key, value.strip()))
            displayed_text.add(value.strip())
    return fields, displayed_text, presentation_keys


def _fields_to_render(result, display_fields, displayed_text, presentation_keys,
                      duplicate_filter):
    fields = {}
    display_keys = presentation_keys | {key for key, _value in display_fields}
    for key, value in result.items():
        if key in {"success", "message", "meta"} or key in display_keys:
            continue
        if display_fields and key not in HUMAN_ALWAYS_VISIBLE_WITH_DISPLAY:
            continue
        cleaned = duplicate_filter(value, displayed_text)
        if not _has_content(cleaned):
            continue
        if key == "details" and isinstance(cleaned, dict):
            for detail_key, detail_value in cleaned.items():
                fields.setdefault(detail_key, detail_value)
        else:
            fields.setdefault(key, cleaned)
    return fields


def _append_details(lines, fields, labeler, append_value):
    if not fields:
        return
    lines.extend(["", "Details:"])
    for key, value in fields.items():
        append_value(lines, labeler(key), value, indent=2)
