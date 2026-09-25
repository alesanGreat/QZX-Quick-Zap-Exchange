"""Interactive QZX terminal line parsing and command dispatch."""

from __future__ import annotations

import contextlib
import os
import shlex
import sys


def dispatch_terminal_line(terminal, line):
    """Dispatch one interactive line while preserving CLI semantics."""
    try:
        parts = shlex.split(line, posix=(os.name != "nt"))
    except ValueError as exc:
        print(f"Invalid command line: {exc}")
        return
    if not parts:
        return

    command, args = parts[0], parts[1:]
    if command == "help":
        terminal.do_help(args[0] if args else "")
        return
    if command.lower() == "cd":
        _change_directory(terminal, args)
        return
    _execute_qzx_command(terminal, command, args)


def _change_directory(terminal, args):
    if not args:
        os.chdir(os.path.expanduser("~"))
        print(f"Changed to home directory: {os.getcwd()}")
    else:
        try:
            os.chdir(args[0])
            print(f"Changed to directory: {os.getcwd()}")
        except Exception as exc:
            print(f"Error changing directory: {str(exc)}")
    terminal._update_prompt()


def _execute_qzx_command(terminal, command, args):
    try:
        instance = terminal._command_instance(command)
        if instance is None:
            print(f"Unknown command: {command}")
            return
        _invoke_and_render(terminal, instance, command, args)
        terminal._update_prompt()
    except Exception as exc:
        print(f"Error executing command '{command}': {str(exc)}")


def _invoke_and_render(terminal, instance, command, args):
    from qzx.cli import (
        _capture_process_stdout,
        _parse_cli_request,
        _print_json,
        _render_human,
    )

    json_output, _command_name, parsed_args = _parse_cli_request(
        [command, *args]
    )
    stdout_context = (
        _capture_process_stdout()
        if json_output
        else contextlib.nullcontext()
    )
    with stdout_context as captured_stdout:
        result = instance.invoke(parsed_args)

    if json_output:
        progress_output = (
            captured_stdout.getvalue() if captured_stdout else ""
        )
        if progress_output:
            print(progress_output, file=sys.stderr, end="")
        _print_json(result)
    else:
        print(_render_human(result))
