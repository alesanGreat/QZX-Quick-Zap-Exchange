#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
QZX: Quick Zap Exchange - Universal Command Interface for AI Agents
"""

import contextlib
import difflib
import io
import json
import math
import os
import platform
import re
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from qzx.core.command_loader import CommandLoader
from qzx.first_run import claim_first_run_attribution
from qzx.identity import product_attribution


class QZX:
    def __init__(self):
        self.os_type = platform.system().lower()
        try:
            from qzx import __version__
            self.version = __version__
        except ImportError:
            self.version = "unknown"
        
        # Initialize command loader
        self.command_loader = CommandLoader()
        
        # Load modular commands
        self.modular_commands = self.command_loader.discover_commands()
        
        # Legacy built-in commands (will be migrated to modular system)
        self.built_in_commands = {
            # All commands have been migrated to their own files!
        }
        
        # Combine all commands (modular commands take precedence)
        self.commands = {**self.built_in_commands, **self.modular_commands}
    
    def execute(self, command, args=None):
        """Execute a command with arguments"""
        if args is None:
            args = []

        normalized_command = command.lower() if command else ""
        
        # Execute a built-in command
        if command in self.built_in_commands:
            return self.built_in_commands[command](*args)
        
        # Execute a modular command
        cmd_obj = self.command_loader.get_command(command)
        if cmd_obj:
            if normalized_command in {"list", "listcommands", "qzxlistcommands"}:
                cmd_obj.command_loader = self.command_loader
            return cmd_obj.invoke(args)
        
        registered = self.command_loader.get_all_commands()
        suggestions = difflib.get_close_matches(
            normalized_command,
            sorted(registered),
            n=5,
            cutoff=0.5,
        )
        suggestion_text = (
            " Did you mean: {}?".format(", ".join(suggestions))
            if suggestions
            else ""
        )
        return {
            "success": False,
            "error": "Command not found: {}".format(command),
            "error_code": "command_not_found",
            "message": "Command '{}' was not found.{} Use 'qzx list' to see available commands.".format(
                command,
                suggestion_text,
            ),
            "details": {
                "command": command,
                "suggestions": suggestions,
            },
            "meta": {
                "schema_version": 1,
            },
        }
    
    def show_help(self, command=None):
        """Show help through the canonical public help command."""
        from qzx.commands.system.qzx_help import qzxHelp

        help_command = qzxHelp()
        help_command.command_loader = self.command_loader
        return help_command.execute(command)
    
    def list_commands(self, filter_text=None):
        """List all available commands using the canonical list command."""
        from qzx.commands.system.qzx_list_commands import qzxListCommands

        command = qzxListCommands()
        command.command_loader = self.command_loader
        return command.format_result(command.execute(filter_text))


def _json_compatible(value):
    """Return a recursively strict JSON-compatible representation."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else str(value)
    if isinstance(value, dict):
        return {
            str(key): _json_compatible(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_json_compatible(item) for item in value]
    if isinstance(value, set):
        return [
            _json_compatible(item)
            for item in sorted(value, key=lambda item: str(item))
        ]
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            pass
    return str(value)


def _print_json(result):
    print(
        json.dumps(
            _json_compatible(result),
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
        )
    )


_HUMAN_ACRONYMS = {
    "am": "AM",
    "api": "API",
    "cpu": "CPU",
    "dns": "DNS",
    "gpu": "GPU",
    "html": "HTML",
    "id": "ID",
    "ip": "IP",
    "json": "JSON",
    "mb": "MB",
    "mbps": "Mbps",
    "os": "OS",
    "pid": "PID",
    "pm": "PM",
    "qzx": "QZX",
    "ram": "RAM",
    "sha": "SHA",
    "ssl": "SSL",
    "url": "URL",
    "zip": "ZIP",
}
_HUMAN_DISPLAY_FIELDS = ("output", "content", "report", "tree_text", "diff")
_HUMAN_ALWAYS_VISIBLE_WITH_DISPLAY = {
    "error",
    "warning",
    "warnings",
    "next_steps",
    "recommendations",
}


def _human_label(name):
    """Turn a structured field name into a readable terminal label."""
    text = str(name)
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", text):
        return text
    words = text.replace("-", "_").split("_")
    formatted = [
        _HUMAN_ACRONYMS.get(word.lower(), word[:1].upper() + word[1:])
        for word in words
        if word
    ]
    return " ".join(formatted) or "Value"


def _human_scalar(value):
    """Format a scalar without leaking Python container representations."""
    if value is None:
        return "Not available"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return str(value)


def _without_duplicate_text(value, displayed_text):
    """Remove exact text already used as the human presentation."""
    if isinstance(value, str):
        return None if value.strip() in displayed_text else value
    if isinstance(value, dict):
        cleaned = {}
        for key, item in value.items():
            cleaned_item = _without_duplicate_text(item, displayed_text)
            if cleaned_item not in (None, "", [], {}):
                cleaned[key] = cleaned_item
        return cleaned
    if isinstance(value, (list, tuple, set)):
        cleaned = [
            _without_duplicate_text(item, displayed_text)
            for item in value
        ]
        return [
            item
            for item in cleaned
            if item not in (None, "", [], {})
        ]
    return value


def _append_human_value(lines, label, value, indent=0):
    """Append a recursively formatted value to a terminal line buffer."""
    prefix = " " * indent
    if isinstance(value, dict):
        if not value:
            return
        lines.append("{}{}:".format(prefix, label))
        for key, item in value.items():
            _append_human_value(
                lines,
                _human_label(key),
                item,
                indent + 2,
            )
        return

    if isinstance(value, (list, tuple, set)):
        items = list(value)
        if not items:
            lines.append("{}{}: None".format(prefix, label))
            return
        lines.append("{}{}:".format(prefix, label))
        for index, item in enumerate(items, 1):
            item_prefix = " " * (indent + 2)
            if isinstance(item, dict):
                lines.append("{}{}. Item".format(item_prefix, index))
                for key, nested in item.items():
                    _append_human_value(
                        lines,
                        _human_label(key),
                        nested,
                        indent + 5,
                    )
            elif isinstance(item, (list, tuple, set)):
                _append_human_value(
                    lines,
                    "{}. Item".format(index),
                    item,
                    indent + 2,
                )
            else:
                lines.append(
                    "{}- {}".format(item_prefix, _human_scalar(item))
                )
        return

    if isinstance(value, str) and "\n" in value:
        lines.append("{}{}:".format(prefix, label))
        for line in value.rstrip().splitlines():
            lines.append("{}  {}".format(prefix, line))
        return

    lines.append("{}{}: {}".format(prefix, label, _human_scalar(value)))


def _visible_meta(result):
    """Expose meaningful operational metadata, not renderer internals."""
    meta = result.get("meta")
    if not isinstance(meta, dict):
        return None
    return {
        key: value
        for key, value in meta.items()
        if key not in {"command", "duration_ms", "schema_version"}
    }


def _render_human(result):
    """Render one structured result as warm, readable terminal text."""
    if not isinstance(result, dict):
        return _human_scalar(result)

    message = str(result.get("message", "")).strip()
    if not message:
        message = (
            "Command completed successfully."
            if result.get("success") is True
            else "The command could not be completed."
        )

    # Help, command listings, and similar results already carry their complete
    # terminal presentation in a multi-line message.
    if len(message.splitlines()) >= 3:
        return message

    display_fields = []
    displayed_text = {message}
    presentation_keys = set()
    for key in _HUMAN_DISPLAY_FIELDS:
        value = result.get(key)
        if isinstance(value, str) and value.strip():
            presentation_keys.add(key)
        if (
            isinstance(value, str)
            and value.strip()
            and value.strip() not in message
        ):
            display_fields.append((key, value.strip()))
            displayed_text.add(value.strip())

    # Older commands sometimes use another named field for their complete
    # multi-line presentation. Honor it without requiring per-command wiring.
    for key, value in result.items():
        if (
            key not in {"message", "error"}
            and key not in _HUMAN_DISPLAY_FIELDS
            and isinstance(value, str)
            and len(value.strip().splitlines()) >= 3
        ):
            display_fields.append((key, value.strip()))
            displayed_text.add(value.strip())

    lines = [message]
    for key, value in display_fields:
        lines.extend(["", "{}:".format(_human_label(key)), value])

    fields_to_render = {}
    display_keys = presentation_keys | {key for key, _value in display_fields}
    for key, value in result.items():
        if key in {"success", "message", "meta"} or key in display_keys:
            continue
        if display_fields and key not in _HUMAN_ALWAYS_VISIBLE_WITH_DISPLAY:
            continue
        cleaned_value = _without_duplicate_text(value, displayed_text)
        if cleaned_value not in (None, "", [], {}):
            fields_to_render[key] = cleaned_value

    visible_meta = _visible_meta(result)
    if visible_meta:
        fields_to_render["meta"] = visible_meta

    if fields_to_render:
        lines.extend(["", "Details:"])
        for key, value in fields_to_render.items():
            _append_human_value(
                lines,
                _human_label(key),
                value,
                indent=2,
            )

    return "\n".join(lines).rstrip()


def _print_human(result):
    print(_render_human(result))


def _contains_attribution(value):
    """Return whether a result already carries the canonical attribution."""
    attribution = product_attribution()
    if isinstance(value, str):
        return attribution in value
    if isinstance(value, dict):
        return any(_contains_attribution(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(_contains_attribution(item) for item in value)
    return False


def _add_first_run_attribution(result, json_output, first_run):
    """Present the one-time attribution without breaking JSON stdout."""
    if not first_run or _contains_attribution(result):
        return result
    if not json_output:
        print(product_attribution())
        return result

    meta = result.get("meta")
    if not isinstance(meta, dict):
        meta = {}
        result["meta"] = meta
    meta["first_run_attribution"] = product_attribution()
    return result


@contextlib.contextmanager
def _capture_process_stdout():
    """
    Capture Python and child-process stdout.

    ``redirect_stdout`` alone misses native programs such as ``cls``. JSON
    mode must capture those bytes as progress too, or they can corrupt the
    single JSON document written by the CLI.
    """
    captured = io.StringIO()
    original_stdout = sys.stdout
    try:
        stdout_fd = original_stdout.fileno()
    except (AttributeError, io.UnsupportedOperation, OSError):
        with contextlib.redirect_stdout(captured):
            yield captured
        return

    try:
        original_stdout.flush()
        saved_stdout_fd = os.dup(stdout_fd)
    except OSError:
        with contextlib.redirect_stdout(captured):
            yield captured
        return

    try:
        with tempfile.TemporaryFile(mode="w+b") as temporary_stdout:
            try:
                os.dup2(temporary_stdout.fileno(), stdout_fd)
                capture_stream = io.TextIOWrapper(
                    os.fdopen(os.dup(stdout_fd), "wb", closefd=True),
                    encoding=(
                        getattr(original_stdout, "encoding", None) or "utf-8"
                    ),
                    errors="replace",
                    write_through=True,
                )
            except (OSError, ValueError):
                os.dup2(saved_stdout_fd, stdout_fd)
                with contextlib.redirect_stdout(captured):
                    yield captured
                return

            try:
                with contextlib.redirect_stdout(capture_stream):
                    yield captured
            finally:
                try:
                    capture_stream.flush()
                finally:
                    try:
                        capture_stream.close()
                    finally:
                        os.dup2(saved_stdout_fd, stdout_fd)
                        temporary_stdout.seek(0)
                        captured.write(
                            temporary_stdout.read().decode(
                                getattr(original_stdout, "encoding", None)
                                or "utf-8",
                                errors="replace",
                            )
                        )
    finally:
        os.close(saved_stdout_fd)


def _exit_code(result):
    if not isinstance(result, dict):
        return 1
    if result.get("success") is True:
        return 0
    error_code = result.get("error_code")
    if error_code == "usage_error":
        return 2
    if error_code == "command_not_found":
        return 127
    return 1


def _parse_cli_request(arguments):
    """Extract the global output mode without exposing it to commands."""
    json_output = False
    filtered_args = []

    for arg in arguments:
        if arg == "--json" or arg == "-json":
            json_output = True
        else:
            filtered_args.append(arg)

    command = filtered_args[0] if filtered_args else "welcome"
    command_args = filtered_args[1:] if filtered_args else []
    return json_output, command, command_args


def main():
    json_output, command, args = _parse_cli_request(sys.argv[1:])
    first_run = claim_first_run_attribution()

    # Schedule one privacy-documented activation event per QZX version. This
    # always runs out of band and can never alter a command result.
    try:
        from qzx import __version__
        from qzx.telemetry import TELEMETRY_NOTICE, schedule_version_telemetry

        telemetry_status = schedule_version_telemetry(__version__)
        if telemetry_status.get("details", {}).get("notice"):
            print(TELEMETRY_NOTICE, file=sys.stderr)
    except Exception:
        # Telemetry is strictly optional and must never prevent CLI startup.
        pass

    stdout_context = (
        _capture_process_stdout()
        if json_output
        else contextlib.nullcontext()
    )
    with stdout_context as captured_stdout:
        qzx = QZX()
        result = qzx.execute(command, args)

    if not isinstance(result, dict):
        result = {
            "success": False,
            "error": str(result),
            "error_code": "invalid_result_contract",
            "message": str(result),
            "meta": {"schema_version": 1},
        }

    result = _add_first_run_attribution(result, json_output, first_run)

    if json_output:
        progress_output = captured_stdout.getvalue() if captured_stdout else ""
        if progress_output:
            print(progress_output, file=sys.stderr, end="")
        _print_json(result)
    else:
        _print_human(result)

    return _exit_code(result)


if __name__ == "__main__":
    raise SystemExit(main())
