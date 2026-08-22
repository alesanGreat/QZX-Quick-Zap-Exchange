"""Adversarial tests for bounded binary/text classification."""

from __future__ import annotations

import io
import os

from qzx.commands.file.is_file_binary import IsFileBinaryCommand
from qzx.core.file_content_analysis import MAX_SAMPLE_SIZE, MIN_SAMPLE_SIZE


def test_missing_and_non_regular_targets_have_stable_error_codes(tmp_path):
    command = IsFileBinaryCommand()

    missing = command.execute(tmp_path / "missing")
    directory = command.execute(tmp_path)

    assert missing["success"] is False
    assert missing["error_code"] == "file_not_found"
    assert directory["success"] is False
    assert directory["error_code"] == "not_a_regular_file"
    assert directory["details"]["entry_type"] == "directory"


def test_invalid_sample_threshold_and_boolean_fail_before_file_io(tmp_path):
    command = IsFileBinaryCommand()
    target = tmp_path / "target.txt"
    target.write_text("text", encoding="utf-8")

    too_small = command.execute(target, sample_size=MIN_SAMPLE_SIZE - 1)
    too_large = command.execute(target, sample_size=MAX_SAMPLE_SIZE + 1)
    zero_threshold = command.execute(target, binary_threshold=0)
    non_finite_threshold = command.execute(target, binary_threshold=float("nan"))
    excessive_threshold = command.execute(target, binary_threshold=101)
    invalid_follow = command.execute(target, follow_symlinks="sometimes")

    assert too_small["error_code"] == "invalid_sample_size"
    assert too_large["error_code"] == "invalid_sample_size"
    assert zero_threshold["error_code"] == "invalid_binary_threshold"
    assert non_finite_threshold["error_code"] == "invalid_binary_threshold"
    assert excessive_threshold["error_code"] == "invalid_binary_threshold"
    assert invalid_follow["error_code"] == "invalid_follow_symlinks"


def test_empty_file_is_text_with_complete_zero_byte_evidence(tmp_path):
    target = tmp_path / "empty"
    target.write_bytes(b"")

    result = IsFileBinaryCommand().execute(target)

    assert result["success"] is True
    assert result["is_binary"] is False
    assert result["mime_type"] == "text/plain"
    assert result["analyzed_bytes"] == 0
    assert result["details"]["sampling"] == {
        "strategy": "empty_file",
        "budget_bytes": 8192,
        "analyzed_bytes": 0,
        "full_file_analyzed": True,
        "segments": [],
        "short_read_detected": False,
    }
    assert result["details"]["binary_analysis"]["detection_method"] == (
        "empty_file"
    )


def test_utf8_and_utf16_text_are_not_misclassified_as_binary(tmp_path):
    utf8 = tmp_path / "utf8.txt"
    utf16 = tmp_path / "utf16.txt"
    content = "Hola Panamá — αβγ\n" * 200
    utf8.write_text(content, encoding="utf-8")
    utf16.write_text(content, encoding="utf-16")

    utf8_result = IsFileBinaryCommand().execute(utf8, sample_size=3000)
    utf16_result = IsFileBinaryCommand().execute(utf16, sample_size=3000)

    assert utf8_result["is_binary"] is False
    assert utf8_result["details"]["binary_analysis"]["encoding_detected"] == (
        "utf-8"
    )
    assert utf16_result["is_binary"] is False
    assert utf16_result["details"]["binary_analysis"]["encoding_detected"] == (
        "utf-16-le"
    )
    assert utf16_result["details"]["binary_analysis"]["null_byte_count"] > 0
    assert utf16_result["details"]["binary_analysis"]["binary_score"] == 0.0


def test_content_signature_overrides_a_misleading_text_extension(tmp_path):
    target = tmp_path / "image.txt"
    target.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 512)

    result = IsFileBinaryCommand().execute(target)

    assert result["success"] is True
    assert result["is_binary"] is True
    assert result["mime_type"] == "image/png"
    analysis = result["details"]["binary_analysis"]
    assert analysis["detection_method"] == "content_signature"
    assert analysis["signature"]["source"] == "content_signature"
    assert analysis["signature"]["mime_type"] == "image/png"


def test_distributed_sampling_catches_binary_content_hidden_in_the_middle(tmp_path):
    target = tmp_path / "distributed.bin"
    target.write_bytes(b"A" * 5000 + b"\x00" * 5000 + b"B" * 5000)

    result = IsFileBinaryCommand().execute(target, sample_size=3000)

    assert result["success"] is True
    assert result["is_binary"] is True
    sampling = result["details"]["sampling"]
    assert sampling["strategy"] == "distributed_start_middle_end"
    assert sampling["analyzed_bytes"] == 3000
    assert [segment["offset"] for segment in sampling["segments"]] == [
        0,
        7000,
        14000,
    ]
    assert result["details"]["binary_analysis"]["null_byte_count"] == 1000


def test_symlink_target_requires_explicit_opt_in(tmp_path):
    target = tmp_path / "target.txt"
    target.write_text("reviewed target", encoding="utf-8")
    link = tmp_path / "link.txt"
    link.symlink_to(target)

    blocked = IsFileBinaryCommand().execute(link)
    followed = IsFileBinaryCommand().execute(link, follow_symlinks=True)

    assert blocked["success"] is False
    assert blocked["error_code"] == "symlink_path_blocked"
    assert blocked["details"]["blocked_component"] == str(link.absolute())
    assert followed["success"] is True
    assert followed["is_binary"] is False
    assert followed["details"]["target"]["followed_symlink"] is True
    assert followed["analyzed_path"] == str(target.resolve())


def test_read_failure_is_structured_and_preserves_target_evidence(tmp_path):
    target = tmp_path / "unreadable.txt"
    target.write_text("content", encoding="utf-8")

    def refuse_open(_path, _mode):
        raise PermissionError("synthetic read denial")

    result = IsFileBinaryCommand(open_file=refuse_open).execute(target)

    assert result["success"] is False
    assert result["error_code"] == "file_read_failed"
    assert result["error"] == "PermissionError: synthetic read denial"
    assert result["details"]["file_path"] == str(target.absolute())


def test_short_sample_stream_prevents_a_stale_binary_conclusion(tmp_path):
    target = tmp_path / "changing.bin"
    target.write_bytes(b"ABCD")

    def shorter_open(_path, _mode):
        return io.BytesIO(b"A")

    result = IsFileBinaryCommand(open_file=shorter_open).execute(target)

    assert result["success"] is False
    assert result["error_code"] == "file_changed_during_read"
    assert "no classification was published" in result["message"]


def test_raw_bytes_empty_and_nul_paths_are_rejected_without_filesystem_access(
    tmp_path,
):
    command = IsFileBinaryCommand()

    raw_bytes = command.execute(os.fsencode(tmp_path / "bytes"))
    empty = command.execute("")
    nul = command.execute("bad\x00path")

    assert raw_bytes["error_code"] == "invalid_file_path"
    assert empty["error_code"] == "invalid_file_path"
    assert nul["error_code"] == "invalid_file_path"
