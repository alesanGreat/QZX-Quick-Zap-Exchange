"""Incremental Unicode logical-line scanner for countLines."""

from __future__ import annotations

import codecs

from qzx.core.file_content_analysis import (
    FileChangedDuringReadError,
    regular_file_fingerprint,
)


def count_stream(command, target, encoding):
    """Count logical lines with constant state and stable-file evidence."""
    initial_fingerprint = regular_file_fingerprint(target.analyzed_path)
    if initial_fingerprint != target.fingerprint:
        raise FileChangedDuringReadError(
            "The file changed between validation and line scanning."
        )

    decoder = codecs.getincrementaldecoder(encoding)(errors="strict")
    state = _initial_state(command)
    with command._open_file(target.analyzed_path, "rb") as file_handle:
        _consume_stream(command, file_handle, decoder, state)
    _finalize_pending_line(command, state)

    final_fingerprint = regular_file_fingerprint(target.analyzed_path)
    if state["bytes_scanned"] != target.file_size:
        raise FileChangedDuringReadError(
            "The bytes scanned no longer match the validated file size."
        )
    if final_fingerprint != initial_fingerprint:
        raise FileChangedDuringReadError(
            "The file changed while logical lines were being counted."
        )

    return _public_scan_state(state)


def _initial_state(command):
    return {
        "line_count": 0,
        "non_blank_line_count": 0,
        "blank_line_count": 0,
        "empty_line_count": 0,
        "whitespace_only_line_count": 0,
        "max_line_length_characters": 0,
        "current_line_length": 0,
        "current_line_has_non_whitespace": False,
        "pending_cr": False,
        "at_text_start": True,
        "ends_with_line_break": False,
        "bytes_scanned": 0,
        "newline_counts": {
            "crlf": 0,
            "cr": 0,
            **{name: 0 for name in command._UNICODE_LINE_BREAKS.values()},
        },
    }


def _consume_stream(command, file_handle, decoder, state):
    while True:
        chunk = file_handle.read(command._CHUNK_SIZE)
        if not chunk:
            break
        state["bytes_scanned"] += len(chunk)
        command._consume_text(_decode(decoder, chunk, state), state)
    command._consume_text(_decode(decoder, b"", state, final=True), state)


def _decode(decoder, chunk, state, final=False):
    try:
        return decoder.decode(chunk, final=final)
    except UnicodeDecodeError as exc:
        exc.qzx_bytes_scanned = state["bytes_scanned"]
        raise


def consume_text(command, text, state):
    """Consume decoded text while preserving cross-chunk CRLF state."""
    for character in text:
        if state["at_text_start"]:
            state["at_text_start"] = False
            if character == "\ufeff":
                continue

        if state["pending_cr"]:
            state["pending_cr"] = False
            if character == "\n":
                state["newline_counts"]["crlf"] += 1
                state["ends_with_line_break"] = True
                continue
            state["newline_counts"]["cr"] += 1

        if character == "\r":
            command._finish_line(state)
            state["pending_cr"] = True
            state["ends_with_line_break"] = True
            continue

        newline_name = command._UNICODE_LINE_BREAKS.get(character)
        if newline_name is not None:
            command._finish_line(state)
            state["newline_counts"][newline_name] += 1
            state["ends_with_line_break"] = True
            continue

        state["current_line_length"] += 1
        if not character.isspace():
            state["current_line_has_non_whitespace"] = True
        state["ends_with_line_break"] = False


def finish_line(state):
    """Finalize one logical line into the aggregate counters."""
    line_length = state["current_line_length"]
    state["line_count"] += 1
    state["max_line_length_characters"] = max(
        state["max_line_length_characters"],
        line_length,
    )
    if state["current_line_has_non_whitespace"]:
        state["non_blank_line_count"] += 1
    else:
        state["blank_line_count"] += 1
        if line_length == 0:
            state["empty_line_count"] += 1
        else:
            state["whitespace_only_line_count"] += 1
    state["current_line_length"] = 0
    state["current_line_has_non_whitespace"] = False


def _finalize_pending_line(command, state):
    if state["pending_cr"]:
        state["newline_counts"]["cr"] += 1
        state["pending_cr"] = False
    if state["current_line_length"]:
        command._finish_line(state)
        state["ends_with_line_break"] = False


def _public_scan_state(state):
    state.pop("current_line_length")
    state.pop("current_line_has_non_whitespace")
    state.pop("pending_cr")
    state.pop("at_text_start")
    state["full_content_scanned"] = True
    state["memory_policy"] = "incremental_decoder_and_constant_line_state"
    state["newline_sequence_count"] = sum(state["newline_counts"].values())
    return state
