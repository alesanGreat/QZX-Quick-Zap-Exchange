#!/usr/bin/env python

"""Behavioral and output-contract tests for compareFiles."""

from qzx.commands.development.compare_files import CompareFilesCommand


def _write_pair(tmp_path, first, second):
    first_path = tmp_path / "first.txt"
    second_path = tmp_path / "second.txt"
    first_path.write_text(first, encoding="utf-8")
    second_path.write_text(second, encoding="utf-8")
    return first_path, second_path


def _assert_public_contract(result, success):
    assert result["success"] is success
    assert isinstance(result["message"], str)
    assert result["message"]


def test_declared_schema_documents_every_mode_and_failure():
    properties = CompareFilesCommand.result_schema["properties"]

    assert {
        "success",
        "message",
        "error",
        "error_code",
        "remediation",
        "file1",
        "file2",
        "mode",
        "identical",
        "added_lines",
        "removed_lines",
        "total_changes",
        "diff",
        "similarity",
        "lines_file1",
        "lines_file2",
        "identical_lines",
        "changes",
        "summary",
        "content_type",
        "comparison_basis",
        "byte_identical",
        "bytes_file1",
        "bytes_file2",
        "max_bytes",
        "encoding_file1",
        "encoding_file2",
        "encoding_confidence_file1",
        "encoding_confidence_file2",
        "sha256_file1",
        "sha256_file2",
        "similarity_available",
    } == set(properties)
    assert properties["mode"]["enum"] == ["full", "summary", "percent"]


def test_full_mode_reports_identical_files_with_zero_changes(tmp_path):
    first_path, second_path = _write_pair(
        tmp_path,
        "same\ncontent\n",
        "same\ncontent\n",
    )

    result = CompareFilesCommand().execute(first_path, second_path, "full")

    _assert_public_contract(result, True)
    assert result["mode"] == "full"
    assert result["identical"] is True
    assert result["total_changes"] == 0
    assert result["diff"] == ""
    assert result["content_type"] == "text"
    assert result["byte_identical"] is True
    assert result["encoding_file1"] == "utf-8"
    assert result["sha256_file1"] == result["sha256_file2"]


def test_full_mode_returns_a_structured_diff(tmp_path):
    first_path, second_path = _write_pair(
        tmp_path,
        "same\nbefore\n",
        "same\nafter\n",
    )

    result = CompareFilesCommand().execute(first_path, second_path, "full")

    _assert_public_contract(result, True)
    assert result["identical"] is False
    assert result["added_lines"] == 1
    assert result["removed_lines"] == 1
    assert result["total_changes"] == 2
    assert "Differences between" in result["diff"]
    assert "Added lines: 1" in result["diff"]
    assert "\n\n-before" not in result["diff"]
    assert "\n-before\n+after\n" in result["diff"]
    assert result["content_type"] == "text"
    assert result["byte_identical"] is False
    assert result["bytes_file1"] == first_path.stat().st_size
    assert result["max_bytes"] == CompareFilesCommand.DEFAULT_MAX_BYTES


def test_summary_and_percent_modes_include_context(tmp_path):
    first_path, second_path = _write_pair(
        tmp_path,
        "same\nbefore\n",
        "same\nafter\n",
    )
    command = CompareFilesCommand()

    summary = command.execute(first_path, second_path, "SUMMARY")
    percent = command.execute(first_path, second_path, "percent")

    for result, mode in ((summary, "summary"), (percent, "percent")):
        _assert_public_contract(result, True)
        assert result["mode"] == mode
        assert result["file1"] == str(first_path)
        assert result["file2"] == str(second_path)
        assert 0 <= result["similarity"] <= 100
    assert "Difference summary" in summary["summary"]
    assert "Similarity between" in percent["message"]


def test_binary_files_are_compared_without_lossy_text_replacement(tmp_path):
    first_path = tmp_path / "first.bin"
    second_path = tmp_path / "second.bin"
    first_path.write_bytes(b"\x00\x80\xff")
    second_path.write_bytes(b"\x00\x81\xff")

    result = CompareFilesCommand().execute(first_path, second_path, "full")

    _assert_public_contract(result, True)
    assert result["content_type"] == "binary"
    assert result["comparison_basis"] == "exact_bytes_and_sha256"
    assert result["identical"] is False
    assert result["byte_identical"] is False
    assert result["sha256_file1"] != result["sha256_file2"]
    assert result["similarity_available"] is False
    assert "similarity" not in result
    assert "text diff" in result["message"]


def test_non_utf8_text_is_decoded_strictly_and_compared(tmp_path):
    first_path = tmp_path / "first.txt"
    second_path = tmp_path / "second.txt"
    first_path.write_bytes("café\nbefore\n".encode("cp1252"))
    second_path.write_bytes("café\nafter\n".encode("cp1252"))

    result = CompareFilesCommand().execute(first_path, second_path, "full")

    _assert_public_contract(result, True)
    assert result["content_type"] == "text"
    assert result["encoding_file1"] in {"iso-8859-1", "windows-1252"}
    assert 0 <= result["encoding_confidence_file1"] <= 1
    assert result["added_lines"] == 1
    assert result["removed_lines"] == 1
    assert "\ufffd" not in result["diff"]


def test_malformed_encoding_confidence_does_not_crash_comparison(tmp_path):
    class MalformedDetectorCommand(CompareFilesCommand):
        @classmethod
        def _decode_text(cls, data):
            return super()._decode_text(
                data,
                detect_encoding=lambda _data: {
                    "encoding": "latin-1",
                    "confidence": "unknown",
                },
            )

    first_path = tmp_path / "first.bin"
    second_path = tmp_path / "second.bin"
    first_path.write_bytes(b"\x80ambiguous first")
    second_path.write_bytes(b"\x80ambiguous second")

    result = MalformedDetectorCommand().execute(first_path, second_path)

    _assert_public_contract(result, True)
    assert result["content_type"] == "binary"
    assert result["similarity_available"] is False


def test_textual_and_byte_identity_are_reported_separately(tmp_path):
    first_path = tmp_path / "utf8.txt"
    second_path = tmp_path / "utf16.txt"
    first_path.write_bytes(b"same\n")
    second_path.write_bytes("same\n".encode("utf-16"))

    result = CompareFilesCommand().execute(first_path, second_path, "full")

    _assert_public_contract(result, True)
    assert result["content_type"] == "text"
    assert result["identical"] is True
    assert result["byte_identical"] is False
    assert result["encoding_file1"] == "utf-8"
    assert result["encoding_file2"] == "utf-16"
    assert "byte encodings differ" in result["message"]


def test_percent_mode_never_calls_distinct_high_similarity_files_identical(
    tmp_path,
):
    lines = [f"line {index}\n" for index in range(20_000)]
    changed_lines = lines.copy()
    changed_lines[len(changed_lines) // 2] = "one changed line\n"
    first_path, second_path = _write_pair(
        tmp_path,
        "".join(lines),
        "".join(changed_lines),
    )

    result = CompareFilesCommand().execute(first_path, second_path, "percent")

    _assert_public_contract(result, True)
    assert result["similarity"] >= 99.99
    assert result["identical"] is False
    assert result["byte_identical"] is False


def test_size_limit_bounds_reads_and_has_an_explicit_override(tmp_path):
    first_path, second_path = _write_pair(tmp_path, "12345", "12345")
    command = CompareFilesCommand()

    blocked = command.execute(first_path, second_path, max_bytes=4)
    allowed = command.execute(first_path, second_path, max_bytes="5")
    invalid = command.execute(first_path, second_path, max_bytes=0)
    fractional = command.execute(first_path, second_path, max_bytes=5.5)

    _assert_public_contract(blocked, False)
    assert blocked["error_code"] == "file_too_large"
    assert blocked["bytes_file1"] == 5
    assert blocked["max_bytes"] == 4
    assert "larger positive max_bytes" in blocked["remediation"]

    _assert_public_contract(allowed, True)
    assert allowed["max_bytes"] == 5

    _assert_public_contract(invalid, False)
    assert invalid["error_code"] == "invalid_max_bytes"

    _assert_public_contract(fractional, False)
    assert fractional["error_code"] == "invalid_max_bytes"


def test_failures_keep_message_and_remediation(tmp_path):
    command = CompareFilesCommand()
    missing = tmp_path / "missing.txt"
    existing = tmp_path / "existing.txt"
    existing.write_text("content\n", encoding="utf-8")

    missing_result = command.execute(missing, existing)
    directory_result = command.execute(tmp_path, existing)
    invalid_mode_result = command.execute(existing, existing, "unknown")
    invalid_path_result = command.execute(None, existing)
    invalid_size_result = command.execute(existing, existing, max_bytes="many")

    for result in (
        missing_result,
        directory_result,
        invalid_mode_result,
        invalid_path_result,
        invalid_size_result,
    ):
        _assert_public_contract(result, False)
        assert result["error"] == result["message"]
        assert result["error_code"]
        assert result["remediation"]
    assert "does not exist" in missing_result["message"]
    assert "not a file" in directory_result["message"]
    assert "Use 'full', 'summary', or 'percent'" in invalid_mode_result["message"]
    assert "strings or path-like" in invalid_path_result["message"]
    assert "positive integer" in invalid_size_result["message"]
