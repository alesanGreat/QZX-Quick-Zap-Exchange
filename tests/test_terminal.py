"""Deterministic public-contract tests for the interactive terminal command."""

import os

from qzx.commands.system.terminal import QZXTerminal, TerminalCommand


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


class _IndexedLoader:
    def get_indexed_commands(self):
        return [
            {
                "name": "alphaCommand",
                "description": "Alpha description",
                "category": "system",
            },
            {
                "name": "betaCommand",
                "description": "Beta description",
                "category": "file",
            },
        ]


class _HelpFixtureCommand:
    description = "Fixture help description"
    parameters = [
        {
            "name": "value",
            "description": "Fixture value",
            "required": False,
            "default": "demo",
        }
    ]
    examples = [
        {
            "command": "qzx fixture demo",
            "description": "Fixture example",
        }
    ]


def test_interactive_terminal_cd_updates_directory_and_prompt(
    tmp_path,
    monkeypatch,
    capsys,
):
    child = tmp_path / "child"
    child.mkdir()
    monkeypatch.chdir(tmp_path)
    terminal = object.__new__(QZXTerminal)
    terminal._update_prompt = lambda: setattr(terminal, "prompt_updated", True)

    terminal.default("cd child")

    assert os.getcwd() == str(child)
    assert terminal.prompt_updated is True
    assert "Changed to directory" in capsys.readouterr().out


def test_interactive_terminal_general_help_uses_indexed_catalog(capsys):
    terminal = object.__new__(QZXTerminal)
    terminal.command_loader = _IndexedLoader()
    terminal.commands = {}

    terminal.do_help("")

    output = capsys.readouterr().out
    assert "Available QZX commands" in output
    assert "alphaCommand" in output
    assert "betaCommand" in output
    assert "TERMINAL COMMANDS" in output


def test_interactive_terminal_specific_help_preserves_metadata(capsys):
    terminal = object.__new__(QZXTerminal)
    terminal.commands = {"fixture": _HelpFixtureCommand}
    terminal.command_loader = _IndexedLoader()

    terminal.do_help("fixture")

    output = capsys.readouterr().out
    assert "Command: fixture" in output
    assert "Fixture help description" in output
    assert "Fixture value" in output
    assert "Default: demo" in output
    assert "qzx fixture demo" in output
