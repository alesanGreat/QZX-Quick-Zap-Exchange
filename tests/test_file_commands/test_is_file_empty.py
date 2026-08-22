"""Streaming, encoding, and race-evidence tests for isFileEmpty."""

from __future__ import annotations

import io

from qzx.commands.file.is_file_empty import IsFileEmptyCommand


def test_missing_and_directory_targets_have_stable_error_codes(tmp_path):
    command = IsFileEmptyCommand()

    missing = command.execute(tmp_path / "missing")
    directory = command.execute(tmp_path)

    assert missing["success"] is False
    assert missing["error_code"] == "file_not_found"
    assert directory["success"] is False
    assert directory["error_code"] == "not_a_regular_file"


def test_zero_byte_file_needs_no_content_read(tmp_path):
    target = tmp_path / "empty.txt"
    target.write_bytes(b"")

    def unexpected_open(_path, _mode):
        raise AssertionError("zero-byte proof must not open the file")

    result = IsFileEmptyCommand(open_file=unexpected_open).execute(
        target,
        consider_whitespace=True,
    )

    assert result["success"] is True
    assert result["is_empty"] is True
    assert result["is_whitespace_only"] is True
    assert result["details"]["emptiness_basis"] == "zero_bytes"
    assert result["details"]["whitespace_scan_bytes"] == 0


def test_nonzero_size_proves_nonempty_when_whitespace_mode_is_disabled(tmp_path):
    target = tmp_path / "nonempty.txt"
    target.write_text("content", encoding="utf-8")

    def unexpected_open(_path, _mode):
        raise AssertionError("size-only mode must not open the file")

    result = IsFileEmptyCommand(open_file=unexpected_open).execute(target)

    assert result["success"] is True
    assert result["is_empty"] is False
    assert "is_whitespace_only" not in result
    assert result["details"]["emptiness_basis"] == "nonzero_size"
    assert result["details"]["full_content_scanned"] is False


def test_utf8_and_utf16_unicode_whitespace_are_streamed_as_empty(tmp_path):
    utf8 = tmp_path / "utf8.txt"
    utf16 = tmp_path / "utf16.txt"
    whitespace = " \t\n\r\u2003" * 20000
    utf8.write_text(whitespace, encoding="utf-8")
    utf16.write_text(whitespace, encoding="utf-16")

    utf8_result = IsFileEmptyCommand().execute(utf8, True)
    utf16_result = IsFileEmptyCommand().execute(utf16, True)

    assert utf8_result["success"] is True
    assert utf8_result["is_empty"] is True
    assert utf8_result["is_whitespace_only"] is True
    assert utf8_result["details"]["text_encoding"] == "utf-8"
    assert utf8_result["details"]["full_content_scanned"] is True
    assert utf8_result["details"]["whitespace_scan_bytes"] == utf8.stat().st_size
    assert utf16_result["success"] is True
    assert utf16_result["is_empty"] is True
    assert utf16_result["is_whitespace_only"] is True
    assert utf16_result["details"]["text_encoding"] == "utf-16-le"
    assert utf16_result["details"]["whitespace_scan_bytes"] == (
        utf16.stat().st_size
    )


def test_non_whitespace_content_stops_the_full_scan_early(tmp_path):
    target = tmp_path / "large.txt"
    target.write_bytes(b"X" + b" " * (1024 * 1024))

    result = IsFileEmptyCommand().execute(target, True)

    assert result["success"] is True
    assert result["is_empty"] is False
    assert result["is_whitespace_only"] is False
    assert result["details"]["emptiness_basis"] == "non_whitespace_content"
    assert result["details"]["whitespace_scan_status"] == (
        "non_whitespace_found"
    )
    assert result["details"]["first_non_whitespace_codepoint"] == "U+0058"
    assert result["details"]["whitespace_scan_bytes"] < target.stat().st_size
    assert result["details"]["full_content_scanned"] is False


def test_binary_signature_proves_nonempty_without_whitespace_stream(tmp_path):
    target = tmp_path / "image.txt"
    target.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 512)

    result = IsFileEmptyCommand().execute(target, True)

    assert result["success"] is True
    assert result["is_empty"] is False
    assert result["is_whitespace_only"] is False
    assert result["details"]["emptiness_basis"] == (
        "binary_content_signature"
    )
    assert result["details"]["whitespace_scan_status"] == "not_text"
    assert result["details"]["whitespace_scan_bytes"] == 0


def test_incomplete_utf16_sequence_is_not_silently_treated_as_whitespace(tmp_path):
    target = tmp_path / "broken-utf16.txt"
    target.write_bytes(b"\xff\xfe ")

    result = IsFileEmptyCommand().execute(target, True)

    assert result["success"] is True
    assert result["is_empty"] is False
    assert result["is_whitespace_only"] is False
    assert result["details"]["emptiness_basis"] == "decode_error"
    assert result["details"]["whitespace_scan_status"] == "decode_error"
    assert "UnicodeDecodeError" in result["details"]["decode_error"]


def test_symlink_target_requires_explicit_review(tmp_path):
    target = tmp_path / "target.txt"
    target.write_text("   \n", encoding="utf-8")
    link = tmp_path / "reviewed-link.txt"
    link.symlink_to(target)

    blocked = IsFileEmptyCommand().execute(link, True)
    followed = IsFileEmptyCommand().execute(link, True, True)

    assert blocked["success"] is False
    assert blocked["error_code"] == "symlink_path_blocked"
    assert followed["success"] is True
    assert followed["is_empty"] is True
    assert followed["details"]["target"]["followed_symlink"] is True
    assert followed["analyzed_path"] == str(target.resolve())


def test_read_failure_is_structured_instead_of_becoming_false_nonempty(tmp_path):
    target = tmp_path / "unreadable.txt"
    target.write_text("   ", encoding="utf-8")

    def refuse_open(_path, _mode):
        raise PermissionError("synthetic read denial")

    result = IsFileEmptyCommand(open_file=refuse_open).execute(target, True)

    assert result["success"] is False
    assert result["error_code"] == "file_read_failed"
    assert result["error"] == "PermissionError: synthetic read denial"
    assert result["details"]["phase"] == "sampling"


def test_short_replacement_stream_prevents_a_whitespace_only_conclusion(tmp_path):
    target = tmp_path / "changing.txt"
    target.write_bytes(b"    ")

    open_count = 0

    def shorter_on_full_scan(path, mode):
        nonlocal open_count
        open_count += 1
        if open_count == 1:
            return open(path, mode)
        return io.BytesIO(b" ")

    result = IsFileEmptyCommand(open_file=shorter_on_full_scan).execute(
        target,
        True,
    )

    assert result["success"] is False
    assert result["error_code"] == "file_changed_during_read"
    assert result["details"]["validated_size"] == 4
    assert result["details"]["whitespace_scan_bytes"] == 1


def test_short_sample_stream_prevents_a_stale_emptiness_conclusion(tmp_path):
    target = tmp_path / "changing.txt"
    target.write_bytes(b"    ")

    def shorter_open(_path, _mode):
        return io.BytesIO(b" ")

    result = IsFileEmptyCommand(open_file=shorter_open).execute(target, True)

    assert result["success"] is False
    assert result["error_code"] == "file_changed_during_read"
    assert result["details"]["phase"] == "sampling"


def test_invalid_booleans_and_paths_are_rejected(tmp_path):
    command = IsFileEmptyCommand()

    invalid_whitespace = command.execute(
        tmp_path,
        consider_whitespace="sometimes",
    )
    invalid_follow = command.execute(tmp_path, follow_symlinks="sometimes")
    raw_bytes = command.execute(bytes(str(tmp_path), encoding="utf-8"))
    empty = command.execute("")
    nul = command.execute("bad\x00path")

    assert invalid_whitespace["error_code"] == "invalid_consider_whitespace"
    assert invalid_follow["error_code"] == "invalid_follow_symlinks"
    assert raw_bytes["error_code"] == "invalid_file_path"
    assert empty["error_code"] == "invalid_file_path"
    assert nul["error_code"] == "invalid_file_path"
