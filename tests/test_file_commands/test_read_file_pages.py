"""Faithful text reading, byte budgets and resumable offsets for AI workflows."""

import codecs
from contextlib import contextmanager
import io
import os

import pytest

from qzx.commands.file.read_file import ReadFileCommand
from qzx.commands.file import _read_file_page as page_io
from qzx.commands.file._read_file_text import DEFAULT_READ_BYTES, MAX_READ_BYTES


TEXT = "Alejandro Sánchez\r\nDiseño 日本語 😀\nÚltima línea"
BOM_CODECS = [
    (b"", "utf-8"), (codecs.BOM_UTF8, "utf-8"),
    (codecs.BOM_UTF16_LE, "utf-16-le"),
    (codecs.BOM_UTF16_BE, "utf-16-be"),
    (codecs.BOM_UTF32_LE, "utf-32-le"),
    (codecs.BOM_UTF32_BE, "utf-32-be"),
]


def _file(tmp_path, data):
    path = tmp_path / "Sánchez sample.txt"
    path.write_bytes(data)
    return path


@pytest.mark.parametrize("bom,codec", BOM_CODECS)
def test_bom_text_is_exact_and_line_endings_are_not_rewritten(tmp_path, bom, codec):
    data = bom + TEXT.encode(codec)
    path = _file(tmp_path, data)
    result = ReadFileCommand().execute(path)
    assert result["success"] is True
    assert result["content"] == TEXT
    assert result["details"]["encoding"] == codec
    assert result["details"]["bytes_consumed"] == len(data)
    assert result["details"]["total_lines"] == 3
    assert result["details"]["entire_file_read"] is True
    assert result["details"]["next_read"] is None
    assert path.read_bytes() == data


@pytest.mark.parametrize("bom,codec", BOM_CODECS)
@pytest.mark.parametrize("budget", [8, 9, 13, 17, 31])
@pytest.mark.parametrize("max_lines", [None, 1, 2])
def test_all_pages_reassemble_exact_unicode_without_overlap(tmp_path, bom, codec, budget, max_lines):
    path = _file(tmp_path, bom + TEXT.encode(codec))
    options = {"file_path": path, "max_bytes": budget, "max_lines": max_lines}
    output = []
    previous = -1
    fingerprints = []
    for _ in range(100):
        result = ReadFileCommand().execute(**options)
        assert result["success"] is True, result
        details = result["details"]
        assert details["offset"] > previous
        previous = details["offset"]
        assert details["source_bytes_read"] <= budget + 4
        output.append(result["content"])
        fingerprints.append(details["fingerprint"])
        options = details["next_read"]
        if options is None:
            assert details["read_complete"] is True
            break
    else:
        pytest.fail("Continuation did not make progress")
    assert "".join(output) == TEXT
    assert all(value == fingerprints[0] for value in fingerprints)


@pytest.mark.parametrize("codec", ["cp1252", "latin-1", "cp437", "cp850"])
def test_explicit_legacy_encoding_preserves_accents(tmp_path, codec):
    text = "Alejandro Sánchez\nDiseño"
    path = _file(tmp_path, text.encode(codec))
    result = ReadFileCommand().execute(path, encoding=codec)
    assert result["success"] is True
    assert result["content"] == text


def test_invalid_utf8_never_returns_replacement_characters_as_success(tmp_path):
    result = ReadFileCommand().execute(_file(tmp_path, b"name: S\xe1nchez"))
    assert result["success"] is False
    assert result["error_code"] == "decode_failed"
    assert "--encoding" in result["message"]
    assert "content" not in result


@pytest.mark.parametrize("value", [-1, 1.5, True, False, float("nan"), float("inf"), "1.5", {}, []])
def test_max_lines_is_a_real_nonnegative_integer(tmp_path, value):
    result = ReadFileCommand().execute(_file(tmp_path, b"one\ntwo"), max_lines=value)
    assert result["success"] is False
    assert result["error_code"] == "invalid_max_lines"


@pytest.mark.parametrize("field,value", [
    ("max_bytes", 0), ("max_bytes", MAX_READ_BYTES + 1), ("max_bytes", 1.5),
    ("max_bytes", True), ("offset", -1), ("offset", True), ("offset", 1.5),
    ("encoding", None), ("encoding", ""), ("encoding", "nonsense-encoding"),
])
def test_invalid_options_are_explicit_failures(tmp_path, field, value):
    result = ReadFileCommand().execute(_file(tmp_path, b"abc"), **{field: value})
    assert result["success"] is False
    assert result["error_code"] == f"invalid_{field}"


@pytest.mark.parametrize("encoding", ["base64_codec", "rot_13", "iso2022_jp"])
def test_non_resumable_or_non_text_codecs_are_not_accepted(tmp_path, encoding):
    result = ReadFileCommand().execute(_file(tmp_path, b"abc"), encoding=encoding)
    assert result["success"] is False
    assert result["error_code"] == "unsupported_encoding"


def test_large_single_line_is_bounded_by_default(tmp_path):
    path = _file(tmp_path, b"x" * (2 * 1024 * 1024))
    result = ReadFileCommand().execute(path)
    assert result["success"] is True
    details = result["details"]
    assert len(result["content"]) == DEFAULT_READ_BYTES
    assert details["truncated_by"] == "max_bytes"
    assert details["read_complete"] is False
    assert details["ends_with_partial_line"] is True
    assert details["next_read"]["offset"] == DEFAULT_READ_BYTES
    assert details["total_lines"] == "unknown"


def test_line_limit_does_not_decode_invalid_bytes_in_the_following_line(tmp_path):
    result = ReadFileCommand().execute(_file(tmp_path, b"one\n\xffinvalid"), max_lines=1)
    assert result["success"] is True
    assert result["content"] == "one\n"
    assert result["details"]["next_read"]["offset"] == 4


def test_zero_line_request_has_no_content_or_looping_continuation(tmp_path):
    result = ReadFileCommand().execute(_file(tmp_path, b"one\ntwo"), max_lines=0)
    assert result["success"] is True
    assert result["content"] == ""
    assert result["details"]["bytes_consumed"] == 0
    assert result["details"]["next_read"] is None


@pytest.mark.parametrize("data", [b"", codecs.BOM_UTF8, codecs.BOM_UTF16_LE])
def test_empty_text_is_a_complete_zero_line_success(tmp_path, data):
    result = ReadFileCommand().execute(_file(tmp_path, data))
    assert result["success"] is True
    assert result["content"] == ""
    assert result["details"]["total_lines"] == 0
    assert result["details"]["read_complete"] is True


@pytest.mark.parametrize("data,offset,code", [
    (b"abc", 4, "invalid_offset"),
    (codecs.BOM_UTF16_LE + b"a\0", 3, "invalid_offset"),
    (codecs.BOM_UTF8 + b"abc", 1, "invalid_offset"),
    ("á".encode(), 1, "decode_failed"),
])
def test_invalid_offsets_fail_without_fake_success(tmp_path, data, offset, code):
    result = ReadFileCommand().execute(_file(tmp_path, data), offset=offset)
    assert result["success"] is False
    assert result["error_code"] == code


def test_tiny_budget_cannot_create_a_nonprogressing_page(tmp_path):
    result = ReadFileCommand().execute(_file(tmp_path, "😀".encode()), max_bytes=1)
    assert result["success"] is False
    assert result["error_code"] == "read_limit_too_small"


def test_nul_binary_content_is_not_presented_as_a_text_success(tmp_path):
    result = ReadFileCommand().execute(_file(tmp_path, b"header\0binary"))
    assert result["success"] is False
    assert result["error_code"] == "binary_content"


def test_descriptor_change_is_a_failure_not_a_partial_success(tmp_path):
    path = _file(tmp_path, b"abc")
    original = page_io._descriptor_fingerprint
    calls = []
    def changed(stream):
        value = original(stream)
        calls.append(value)
        return value if len(calls) == 1 else (value[0] + 1, *value[1:])
    def opener(target):
        return page_io._open_verified(
            target, descriptor_fingerprint=changed
        )

    def page_reader(file_path, options, format_bytes):
        return page_io.read_file_page(
            file_path, options, format_bytes, opener=opener
        )

    result = ReadFileCommand(page_reader=page_reader).execute(path)
    assert result["success"] is False
    assert result["error_code"] == "file_changed_during_read"
    assert "content" not in result


def test_head_does_not_read_the_entire_following_line(tmp_path):
    data = b"first\n" + b"x" * (2 * 1024 * 1024)
    path = _file(tmp_path, data)
    reads = []
    class TrackedStream(io.BytesIO):
        def read(self, size=-1):
            assert size >= 0, "Unbounded read"
            reads.append(size)
            return super().read(size)
    @contextmanager
    def opened(_target):
        yield TrackedStream(data)
    def page_reader(file_path, options, format_bytes):
        return page_io.read_file_page(
            file_path, options, format_bytes, opener=opened
        )

    result = ReadFileCommand(page_reader=page_reader).execute(path, max_lines=1)
    assert result["content"] == "first\n"
    assert sum(reads) <= DEFAULT_READ_BYTES + 4


if hasattr(os, "mkfifo"):
    def test_fifo_is_rejected_without_waiting_for_a_writer(tmp_path):
        path = tmp_path / "input.pipe"
        os.mkfifo(path)
        result = ReadFileCommand().execute(path)
        assert result["success"] is False
        assert result["error_code"] == "not_a_regular_file"
else:
    def test_fifo_fixture_capability_is_explicit():
        assert not hasattr(os, "mkfifo")


def test_continuation_refuses_an_appended_file(tmp_path):
    path = _file(tmp_path, b"first\nsecond\n")
    first = ReadFileCommand().execute(path, max_lines=1)
    path.write_bytes(b"first\nsecond\nthird\n")
    result = ReadFileCommand().execute(**first["details"]["next_read"])
    assert result["success"] is False
    assert result["error_code"] == "file_changed_since_previous_read"
    assert "content" not in result


def test_continuation_refuses_retargeting_to_another_file(tmp_path):
    first = ReadFileCommand().execute(_file(tmp_path, b"first\nsecond"), max_lines=1)
    other = tmp_path / "other.txt"
    other.write_bytes(b"first\nsecond")
    options = {**first["details"]["next_read"], "file_path": str(other)}
    result = ReadFileCommand().execute(**options)
    assert result["success"] is False
    assert result["error_code"] == "file_changed_since_previous_read"


def test_content_is_not_duplicated_in_json_details(tmp_path):
    result = ReadFileCommand().execute(_file(tmp_path, b"useful content"))
    assert result["content"] == "useful content"
    assert "content" not in result["details"]


def test_zero_line_human_message_does_not_suggest_looping_continuation(tmp_path):
    result = ReadFileCommand().execute(_file(tmp_path, b"content"), max_lines=0)
    assert "Increase max_lines" in result["message"]
    assert "Continue with" not in result["message"]
    assert result["details"]["read_complete"] is False


@pytest.mark.parametrize("value", [True, 12, {}, "", "invalid", "g" * 64])
def test_invalid_expected_fingerprint_is_not_ignored(tmp_path, value):
    result = ReadFileCommand().execute(_file(tmp_path, b"text"), expected_fingerprint=value)
    assert result["success"] is False
    assert result["error_code"] == "invalid_expected_fingerprint"


@pytest.mark.parametrize("codec", ["utf-8", "utf-16-le", "utf-16-be", "utf-32-le", "utf-32-be"])
@pytest.mark.parametrize("text,expected", [
    ("\u0a00\nnext", "\u0a00\n"),
    ("\u0d00\r\nnext", "\u0d00\r\n"),
    ("\u0a0a\rnext", "\u0a0a\r"),
    ("\r\n\r\nnext", "\r\n"),
])
def test_wide_unicode_bytes_do_not_create_false_line_boundaries(tmp_path, codec, text, expected):
    path = _file(tmp_path, text.encode(codec))
    result = ReadFileCommand().execute(path, max_lines=1, encoding=codec)
    assert result["success"] is True, result
    assert result["content"] == expected


def test_permission_failure_is_actionable_and_contains_no_content(tmp_path):
    path = _file(tmp_path, b"text")
    def inaccessible(_target):
        raise PermissionError("test-only permission error")
    def page_reader(file_path, options, format_bytes):
        return page_io.read_file_page(
            file_path, options, format_bytes, opener=inaccessible
        )

    result = ReadFileCommand(page_reader=page_reader).execute(path)
    assert result["success"] is False
    assert result["error_code"] == "permission_denied"
    assert "content" not in result
