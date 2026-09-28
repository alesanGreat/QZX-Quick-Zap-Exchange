#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""QZX: Quick Zap Exchange - Universal Command Interface for AI Agents."""

import contextlib
import json
import sys

from qzx._stdio import configure_utf8_stdio
from qzx.core.cli_rendering import (
    HUMAN_ACRONYMS,
    HUMAN_ALWAYS_VISIBLE_WITH_DISPLAY,
    HUMAN_DISPLAY_FIELDS,
    append_human_value,
    human_label,
    human_scalar,
    json_compatible,
    render_command_catalog,
    render_human,
    visible_meta,
    without_duplicate_text,
)
from qzx.core.command_index import CommandIndexError
from qzx.core.command_loader import CommandLoader
from qzx.core.result_contract import ensure_result_contract
from qzx.core.stdout_capture import capture_process_stdout
from qzx.first_run import claim_first_run_attribution
from qzx.identity import product_attribution
from qzx.telemetry_runtime import schedule_optional_telemetry


class QZX:
    def __init__(self):
        try:
            from qzx import __version__
            self.version = __version__
        except ImportError:
            self.version = "unknown"
        self.command_loader = CommandLoader()
        # Keep a live view of lazily loaded commands. Ordinary invocations
        # import only the requested canonical command.
        self.modular_commands = self.command_loader.commands
        self.built_in_commands = {}
        self.commands = {**self.built_in_commands, **self.modular_commands}

    def execute(self, command, args=None):
        """Execute a built-in or lazily indexed command."""
        args = [] if args is None else args
        normalized_command = command.lower() if command else ""
        if command in self.built_in_commands:
            return self.built_in_commands[command](*args)
        try:
            command_object = self.command_loader.get_command(command)
        except CommandIndexError as exc:
            return _command_index_error(command, exc)
        if command_object:
            if normalized_command == "listcommands":
                command_object.command_loader = self.command_loader
            return command_object.invoke(args)
        return _command_not_found(self.command_loader, command)

    def show_help(self, command=None):
        """Show help through the canonical public help command."""
        from qzx.commands.system.help import HelpCommand

        help_command = HelpCommand()
        help_command.command_loader = self.command_loader
        return help_command.execute(command)

    def list_commands(self, filter_text=None):
        """List all available commands using the canonical list command."""
        from qzx.commands.system.list_commands import ListCommandsCommand

        command = ListCommandsCommand()
        command.command_loader = self.command_loader
        return command.format_result(command.execute(filter_text))


def _command_index_error(command, exc):
    return {
        "success": False,
        "error_code": "command_index_invalid",
        "error": str(exc),
        "message": (
            "QZX could not load its packaged command index. Reinstall "
            "QZX or regenerate the development index."
        ),
        "details": {
            "command": command,
            "remediation": (
                "Run 'python scripts/sync_command_index.py --write' "
                "from a development checkout."
            ),
        },
    }


def _command_not_found(loader, command):
    suggestions = loader.suggest_command_names(command)
    suggestion_text = (
        " Did you mean: {}?".format(", ".join(suggestions)) if suggestions else ""
    )
    return {
        "success": False,
        "error": "Command not found: {}".format(command),
        "error_code": "command_not_found",
        "message": (
            "Command '{}' was not found.{} Use 'qzx listCommands' to see "
            "available commands."
        ).format(command, suggestion_text),
        "details": {"command": command, "suggestions": suggestions},
        "meta": {"schema_version": 1},
    }


def _json_compatible(value):
    """Return a recursively strict JSON-compatible representation."""
    return json_compatible(value)


def _print_json(result):
    """Write one UTF-8 JSON document regardless of the text code page."""
    serialized = json.dumps(
        _json_compatible(result), indent=2, ensure_ascii=False, allow_nan=False
    )
    binary_stdout = getattr(sys.stdout, "buffer", None)
    if binary_stdout is None:
        print(serialized)
        return
    binary_stdout.write((serialized + "\n").encode("utf-8"))
    binary_stdout.flush()


_HUMAN_ACRONYMS = HUMAN_ACRONYMS
_HUMAN_DISPLAY_FIELDS = HUMAN_DISPLAY_FIELDS
_HUMAN_ALWAYS_VISIBLE_WITH_DISPLAY = HUMAN_ALWAYS_VISIBLE_WITH_DISPLAY


def _human_label(name):
    """Turn a structured field name into a readable terminal label."""
    return human_label(name)


def _human_scalar(value):
    """Format a scalar without leaking Python container representations."""
    return human_scalar(value)


def _without_duplicate_text(value, displayed_text):
    """Remove exact text already used as the human presentation."""
    return without_duplicate_text(value, displayed_text)


def _append_human_value(lines, label, value, indent=0):
    """Append a recursively formatted value to a terminal line buffer."""
    return append_human_value(
        lines, label, value, indent, labeler=_human_label, scalar=_human_scalar
    )


def _visible_meta(result):
    """Expose meaningful operational metadata, not renderer internals."""
    return visible_meta(result)


def _render_command_catalog(result, message):
    """Render listCommands from structured data without duplicating JSON."""
    return render_command_catalog(result, message)


def _render_human(result):
    """Render one structured result as warm, readable terminal text."""
    return render_human(
        result,
        scalar=_human_scalar,
        render_catalog=_render_command_catalog,
        labeler=_human_label,
        append_value=_append_human_value,
        meta_filter=_visible_meta,
        duplicate_filter=_without_duplicate_text,
    )


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
    """Capture Python and child-process stdout for one JSON invocation."""
    with capture_process_stdout(sys.stdout) as captured:
        yield captured


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
    for argument in arguments:
        if argument in {"--json", "-json"}:
            json_output = True
        else:
            filtered_args.append(argument)
    command = filtered_args[0] if filtered_args else "welcome"
    command_args = filtered_args[1:] if filtered_args else []
    if command in {"--help", "-h"}:
        command = "help"
    elif command in {"--version", "-V"}:
        command = "version"
    elif any(argument in {"--help", "-h"} for argument in command_args):
        command_args = [command]
        command = "help"
    return json_output, command, command_args


def _execute_requested_command(command, args):
    """Execute one command through the validated lazy command loader."""
    return QZX().execute(command, args)


def _schedule_optional_telemetry(result):
    """Schedule privacy-bounded telemetry after user-visible output is available."""
    schedule_optional_telemetry(usage_result=result)


def _normalize_result(result):
    if isinstance(result, dict):
        return result
    return {
        "success": False,
        "error": str(result),
        "error_code": "invalid_result_contract",
        "message": str(result),
        "meta": {"schema_version": 1},
    }


def _emit_result(result, json_output, captured_stdout):
    if json_output:
        progress_output = captured_stdout.getvalue() if captured_stdout else ""
        if progress_output:
            print(progress_output, file=sys.stderr, end="")
        _print_json(result)
    else:
        _print_human(result)


def main():
    configure_utf8_stdio()
    json_output, command, args = _parse_cli_request(sys.argv[1:])
    first_run = claim_first_run_attribution()
    stdout_context = _capture_process_stdout() if json_output else contextlib.nullcontext()
    with stdout_context as captured_stdout:
        result = _execute_requested_command(command, args)
    result = _normalize_result(result)
    result = _add_first_run_attribution(result, json_output, first_run)
    result = ensure_result_contract(result)
    _emit_result(result, json_output, captured_stdout)
    exit_code = _exit_code(result)
    _schedule_optional_telemetry(result)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
