"""Behavioral tests for shell-free terminal clearing."""

from qzx.commands.system.clear_screen import ClearScreenCommand


class RecordingStream:
    def __init__(self, *, interactive=True, write_error=None):
        self.interactive = interactive
        self.write_error = write_error
        self.writes = []
        self.flush_count = 0

    def isatty(self):
        return self.interactive

    def write(self, value):
        if self.write_error is not None:
            raise self.write_error
        self.writes.append(value)
        return len(value)

    def flush(self):
        self.flush_count += 1


def test_interactive_terminal_uses_one_direct_ansi_sequence():
    stream = RecordingStream()

    result = ClearScreenCommand(stream=stream, environment={}).execute()

    assert result["success"] is True
    assert result["screen_cleared"] is True
    assert result["details"] == {
        "method": "ansi_csi",
        "sequence_written": True,
        "shell_spawned": False,
    }
    assert stream.writes == ["\x1b[2J\x1b[H"]
    assert stream.flush_count == 1


def test_redirected_output_is_not_polluted_with_terminal_control_bytes():
    stream = RecordingStream(interactive=False)

    result = ClearScreenCommand(stream=stream, environment={}).execute()

    assert result["success"] is True
    assert result["screen_cleared"] is False
    assert result["details"]["reason"] == "non_interactive_output"
    assert result["details"]["shell_spawned"] is False
    assert stream.writes == []
    assert stream.flush_count == 0


def test_term_dumb_is_respected_even_for_a_tty():
    stream = RecordingStream()

    result = ClearScreenCommand(
        stream=stream,
        environment={"TERM": "dumb"},
    ).execute()

    assert result["success"] is True
    assert result["screen_cleared"] is False
    assert result["details"]["reason"] == "terminal_declared_dumb"
    assert stream.writes == []


def test_stream_failure_has_a_stable_error_code():
    stream = RecordingStream(write_error=OSError("synthetic terminal failure"))

    result = ClearScreenCommand(stream=stream, environment={}).execute()

    assert result["success"] is False
    assert result["error_code"] == "screen_clear_failed"
    assert result["error"] == "OSError: synthetic terminal failure"
    assert result["screen_cleared"] is False
    assert result["details"]["shell_spawned"] is False
