#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Regression tests for the current single-file countLines contract."""

from __future__ import annotations

import io

from qzx.commands.file.count_lines import CountLinesCommand


def test_empty_file_has_zero_logical_lines(tmp_path):
    target = tmp_path / "empty.txt"
    target.touch()

    result = CountLinesCommand().execute(target)

    assert result["success"] is True
    assert result["line_count"] == 0
    assert result["non_blank_line_count"] == 0
    assert result["blank_line_count"] == 0
    assert result["details"]["bytes_scanned"] == 0
    assert result["details"]["full_content_scanned"] is True


def test_unicode_line_breaks_and_blank_lines_are_counted_logically(tmp_path):
    target = tmp_path / "logical-lines.txt"
    target.write_bytes("alpha\r\n \u2028omega".encode("utf-8"))

    result = CountLinesCommand().execute(target, encoding="utf-8")

    assert result["success"] is True
    assert result["line_count"] == 3
    assert result["non_blank_line_count"] == 2
    assert result["blank_line_count"] == 1
    assert result["empty_line_count"] == 0
    assert result["whitespace_only_line_count"] == 1
    assert result["details"]["newline_counts"]["crlf"] == 1
    assert result["details"]["newline_counts"]["line_separator"] == 1
    assert result["details"]["ends_with_line_break"] is False


def test_terminal_newline_does_not_create_a_phantom_line(tmp_path):
    target = tmp_path / "terminated.txt"
    target.write_bytes(b"one\ntwo\n")

    result = CountLinesCommand().execute(target, encoding="utf-8")

    assert result["success"] is True
    assert result["line_count"] == 2
    assert result["details"]["newline_sequence_count"] == 2
    assert result["details"]["ends_with_line_break"] is True


def test_auto_detection_counts_utf16_text(tmp_path):
    target = tmp_path / "utf16.txt"
    target.write_text("one\ntwo\n", encoding="utf-16")

    result = CountLinesCommand().execute(target)

    assert result["success"] is True
    assert result["encoding"] == "utf-16-le"
    assert result["line_count"] == 2
    assert result["details"]["encoding_source"] == "content_detection"


def test_invalid_encoding_is_a_usage_failure(tmp_path):
    target = tmp_path / "text.txt"
    target.write_bytes(b"text")

    result = CountLinesCommand().execute(target, encoding="definitely-not-a-codec")

    assert result["success"] is False
    assert result["error_code"] == "invalid_encoding"


def test_malformed_explicit_text_fails_without_replacement_characters(tmp_path):
    target = tmp_path / "broken.txt"
    target.write_bytes(b"valid\xffinvalid")

    result = CountLinesCommand().execute(target, encoding="utf-8")

    assert result["success"] is False
    assert result["error_code"] == "text_decode_failed"


def test_short_stream_is_reported_as_a_changed_file(tmp_path):
    target = tmp_path / "changing.txt"
    target.write_bytes(b"four")

    def shorter_open(_path, _mode):
        return io.BytesIO(b"x")

    result = CountLinesCommand(open_file=shorter_open).execute(
        target,
        encoding="utf-8",
    )

    assert result["success"] is False
    assert result["error_code"] == "file_changed_during_read"
    assert "no count was published" in result["message"]
