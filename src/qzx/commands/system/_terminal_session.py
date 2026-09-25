"""TerminalCommand launch validation and session lifecycle."""

from __future__ import annotations

import os


def launch_terminal(command, terminal_factory, prompt, history_file, show_path):
    """Validate terminal options, start one session, and return its result."""
    failure = _option_failure(command, prompt, history_file, show_path)
    if failure is not None:
        return failure
    show_path = _normalized_show_path(command, show_path)
    normalized_history = (
        os.fspath(history_file) if history_file is not None else None
    )
    factory = command._terminal_factory or terminal_factory
    try:
        terminal = factory(prompt, normalized_history, show_path)
        terminal.start()
    except Exception as exc:
        return {
            "success": False,
            "error_code": "terminal_start_failed",
            "error": f"{type(exc).__name__}: {exc}",
            "message": "The interactive QZX terminal could not be started.",
            "details": {
                "history_enabled": normalized_history is not None,
                "show_path": show_path,
            },
        }
    return {
        "success": True,
        "message": "QZX terminal session ended.",
        "details": {
            "prompt": prompt,
            "history_enabled": normalized_history is not None,
            "history_file": normalized_history,
            "show_path": show_path,
        },
    }


def _option_failure(command, prompt, history_file, show_path):
    if not isinstance(prompt, str):
        return {
            "success": False,
            "error_code": "invalid_prompt",
            "error": "prompt must be a string.",
            "message": "Provide a text prompt for the QZX terminal.",
        }
    if history_file is not None and not isinstance(
        history_file,
        (str, os.PathLike),
    ):
        return {
            "success": False,
            "error_code": "invalid_history_file",
            "error": "history_file must be a filesystem path or null.",
            "message": (
                "Provide a history path, or omit history_file to keep "
                "the interactive session ephemeral."
            ),
        }
    if isinstance(show_path, str) and command._parse_bool(show_path) is None:
        return _invalid_show_path(show_path)
    if not isinstance(show_path, (str, bool)):
        return _invalid_show_path(show_path)
    return None


def _normalized_show_path(command, show_path):
    if isinstance(show_path, str):
        return command._parse_bool(show_path)
    return show_path


def _invalid_show_path(value):
    if isinstance(value, str):
        error = f"show_path must be true or false; received '{value}'."
    else:
        error = "show_path must be a boolean."
    return {
        "success": False,
        "error_code": "invalid_show_path",
        "error": error,
        "message": "Choose whether the terminal prompt shows the path.",
    }
