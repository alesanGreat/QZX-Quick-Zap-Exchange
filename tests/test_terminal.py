"""Deterministic public-contract tests for the interactive terminal command."""

from qzx.commands.system.terminal import TerminalCommand


def _recording_factory(record):
    class RecordingTerminal:
        def __init__(self, prompt, history_file, show_path):
            record.update(
                prompt=prompt,
                history_file=history_file,
                show_path=show_path,
            )

        def start(self):
            record["started"] = True

    return RecordingTerminal


def test_public_show_path_false_reaches_the_terminal_session():
    record = {}
    command = TerminalCommand(terminal_factory=_recording_factory(record))

    result = command.invoke(
        [
            "Agent> ",
            "--history_file",
            "session.history",
            "--show_path",
            "false",
        ]
    )

    assert result["success"] is True
    assert result["details"] == {
        "prompt": "Agent> ",
        "history_enabled": True,
        "history_file": "session.history",
        "show_path": False,
    }
    assert record == {
        "prompt": "Agent> ",
        "history_file": "session.history",
        "show_path": False,
        "started": True,
    }


def test_default_terminal_session_is_ephemeral_and_shows_the_path():
    record = {}
    command = TerminalCommand(terminal_factory=_recording_factory(record))

    result = command.invoke([])

    assert result["success"] is True
    assert result["details"]["history_enabled"] is False
    assert result["details"]["history_file"] is None
    assert record["show_path"] is True


def test_invalid_show_path_is_a_usage_error_before_session_start():
    record = {}
    command = TerminalCommand(terminal_factory=_recording_factory(record))

    result = command.invoke(["--show_path", "sometimes"])

    assert result["success"] is False
    assert result["error_code"] == "usage_error"
    assert record == {}


def test_terminal_factory_failure_is_structured():
    def fail_to_start(_prompt, _history_file, _show_path):
        raise OSError("synthetic terminal failure")

    result = TerminalCommand(terminal_factory=fail_to_start).invoke([])

    assert result["success"] is False
    assert result["error_code"] == "terminal_start_failed"
    assert result["error"] == "OSError: synthetic terminal failure"
    assert result["details"] == {
        "history_enabled": False,
        "show_path": True,
    }
