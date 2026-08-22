"""Content-first and optional-libmagic tests for detectFileType."""

from __future__ import annotations

import io

from qzx.commands.file.detect_file_type import DetectFileTypeCommand
from qzx.core.file_content_analysis import MAX_SAMPLE_SIZE, MIN_SAMPLE_SIZE


class BufferMagic:
    def __init__(self, mime_type, description="synthetic libmagic description"):
        self.mime_type = mime_type
        self.description = description
        self.calls = []

    def from_buffer(self, data, *, mime):
        self.calls.append((bytes(data), mime))
        return self.mime_type if mime else self.description


class FailingMagic:
    @staticmethod
    def from_buffer(_data, *, mime):
        raise OSError(f"synthetic libmagic failure mime={mime}")


class FileOnlyMagic:
    def __init__(self):
        self.paths = []

    def from_file(self, path, *, mime):
        self.paths.append((path, mime))
        return "text/plain" if mime else "plain text from file provider"


def test_missing_path_is_reported_even_when_libmagic_is_unavailable(tmp_path):
    result = DetectFileTypeCommand(magic_provider=None).execute(
        tmp_path / "missing"
    )

    assert result["success"] is False
    assert result["error_code"] == "file_not_found"


def test_builtin_png_signature_beats_misleading_extension_without_libmagic(
    tmp_path,
):
    target = tmp_path / "actually-text.txt"
    target.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 512)

    result = DetectFileTypeCommand(magic_provider=None).execute(target, True)

    assert result["success"] is True
    assert result["mime_type"] == "image/png"
    assert result["description"] == "PNG image"
    assert result["is_binary"] is True
    assert result["extension_matches_content"] is False
    assert result["suggested_extension"] == ".png"
    assert result["details"]["detection"]["source"] == "content_signature"
    assert result["details"]["libmagic_available"] is False
    assert result["details"]["sampling"]["full_file_analyzed"] is True


def test_json_text_has_text_category_and_matching_extension(tmp_path):
    target = tmp_path / "payload.json"
    target.write_text('{"hello": "Panamá"}\n', encoding="utf-8")

    result = DetectFileTypeCommand(magic_provider=None).execute(target, True)

    assert result["success"] is True
    assert result["mime_type"] == "application/json"
    assert result["is_binary"] is False
    assert result["extension_matches_content"] is True
    assert result["details"]["categories"] == ["Text"]
    assert result["details"]["common_extensions"] == ["json"]
    assert result["details"]["binary_analysis"]["encoding_detected"] == (
        "utf-8"
    )


def test_ooxml_extension_is_an_explicit_low_confidence_zip_hint(tmp_path):
    target = tmp_path / "unverified.docx"
    target.write_bytes(b"PK\x03\x04" + b"not-a-real-office-package")

    result = DetectFileTypeCommand(magic_provider=None).execute(target, True)

    assert result["success"] is True
    assert result["mime_type"] == (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert result["details"]["detection"]["source"] == (
        "zip_container_plus_extension_hint"
    )
    assert result["details"]["detection"]["confidence"] == 55
    assert result["details"]["container_mime_type"] == "application/zip"
    assert "subtype not verified" in result["description"]
    assert any("inferred from the extension only" in item for item in result["warnings"])


def test_libmagic_can_correct_an_unverified_ooxml_extension_hint(tmp_path):
    target = tmp_path / "actually-zip.docx"
    target.write_bytes(b"PK\x03\x04" + b"generic zip payload")
    provider = BufferMagic("application/zip", "ZIP archive")

    result = DetectFileTypeCommand(magic_provider=provider).execute(target, True)

    assert result["success"] is True
    assert result["mime_type"] == "application/zip"
    assert result["details"]["detection"]["source"] == "libmagic"
    assert result["details"]["builtin_detection"]["source"] == (
        "zip_container_plus_extension_hint"
    )
    assert result["extension_matches_content"] is False
    assert result["suggested_extension"] == ".zip"


def test_libmagic_refines_ambiguous_builtin_detection(tmp_path):
    target = tmp_path / "payload.bin"
    target.write_text("ambiguous text payload", encoding="utf-8")
    provider = BufferMagic("application/pdf; charset=binary", "PDF document")

    result = DetectFileTypeCommand(magic_provider=provider).execute(target, True)

    assert result["success"] is True
    assert result["mime_type"] == "application/pdf"
    assert result["description"] == "PDF document"
    assert result["details"]["detection"]["source"] == "libmagic"
    assert result["details"]["libmagic_mime_type"] == "application/pdf"
    assert result["details"]["libmagic_agrees_with_builtin"] is False
    assert result["extension_matches_content"] is False
    assert result["suggested_extension"] == ".pdf"
    assert [mime for _data, mime in provider.calls] == [True, False]


def test_strong_signature_wins_when_libmagic_disagrees(tmp_path):
    target = tmp_path / "image.png"
    target.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 512)
    provider = BufferMagic("text/plain", "plain text")

    result = DetectFileTypeCommand(magic_provider=provider).execute(target, True)

    assert result["success"] is True
    assert result["mime_type"] == "image/png"
    assert result["details"]["detection"]["source"] == "content_signature"
    assert result["details"]["libmagic_agrees_with_builtin"] is False
    assert any("retained the signature" in warning for warning in result["warnings"])


def test_libmagic_failure_and_malformed_mime_fall_back_without_command_failure(
    tmp_path,
):
    target = tmp_path / "notes.txt"
    target.write_text("plain text", encoding="utf-8")

    failed = DetectFileTypeCommand(magic_provider=FailingMagic()).execute(target)
    malformed = DetectFileTypeCommand(
        magic_provider=BufferMagic("not-a-mime")
    ).execute(target)

    assert failed["success"] is True
    assert failed["mime_type"] == "text/plain"
    assert any("refinement failed" in warning for warning in failed["warnings"])
    assert malformed["success"] is True
    assert malformed["mime_type"] == "text/plain"
    assert any("malformed MIME" in warning for warning in malformed["warnings"])


def test_unknown_libmagic_mime_has_unknown_extension_match_not_false_certainty(
    tmp_path,
):
    target = tmp_path / "payload.custom"
    target.write_text("content", encoding="utf-8")

    result = DetectFileTypeCommand(
        magic_provider=BufferMagic("application/x-qzx-custom")
    ).execute(target, True)

    assert result["success"] is True
    assert result["mime_type"] == "application/x-qzx-custom"
    assert result["extension_matches_content"] is None
    assert result["details"]["extension_match_status"] == "unknown"
    assert result["details"]["common_extensions"] == []
    assert "suggested_extension" not in result


def test_file_only_magic_provider_receives_the_validated_target(tmp_path):
    target = tmp_path / "notes.txt"
    target.write_text("plain text", encoding="utf-8")
    provider = FileOnlyMagic()

    result = DetectFileTypeCommand(magic_provider=provider).execute(target)

    assert result["success"] is True
    assert provider.paths == [
        (str(target.absolute()), True),
        (str(target.absolute()), False),
    ]


def test_invalid_flags_and_sample_sizes_are_structured(tmp_path):
    target = tmp_path / "target.txt"
    target.write_text("text", encoding="utf-8")
    command = DetectFileTypeCommand(magic_provider=None)

    invalid_detail = command.execute(target, detailed_info="sometimes")
    too_small = command.execute(target, sample_size=MIN_SAMPLE_SIZE - 1)
    too_large = command.execute(target, sample_size=MAX_SAMPLE_SIZE + 1)
    invalid_follow = command.execute(target, follow_symlinks="sometimes")

    assert invalid_detail["error_code"] == "invalid_detailed_info"
    assert too_small["error_code"] == "invalid_sample_size"
    assert too_large["error_code"] == "invalid_sample_size"
    assert invalid_follow["error_code"] == "invalid_follow_symlinks"


def test_symlink_is_blocked_by_default_and_can_be_explicitly_followed(tmp_path):
    target = tmp_path / "target.json"
    target.write_text('{"ok": true}\n', encoding="utf-8")
    link = tmp_path / "reviewed-link.json"
    link.symlink_to(target)
    command = DetectFileTypeCommand(magic_provider=None)

    blocked = command.execute(link)
    followed = command.execute(link, follow_symlinks=True)

    assert blocked["success"] is False
    assert blocked["error_code"] == "symlink_path_blocked"
    assert followed["success"] is True
    assert followed["mime_type"] == "application/json"
    assert followed["details"]["target"]["followed_symlink"] is True
    assert followed["analyzed_path"] == str(target.resolve())


def test_short_sample_stream_prevents_a_stale_type_conclusion(tmp_path):
    target = tmp_path / "changing.bin"
    target.write_bytes(b"ABCD")

    def shorter_open(_path, _mode):
        return io.BytesIO(b"A")

    result = DetectFileTypeCommand(
        magic_provider=None,
        open_file=shorter_open,
    ).execute(target)

    assert result["success"] is False
    assert result["error_code"] == "file_changed_during_read"
    assert "no classification was published" in result["message"]


def test_read_failure_is_structured(tmp_path):
    target = tmp_path / "unreadable.txt"
    target.write_text("content", encoding="utf-8")

    def refuse_open(_path, _mode):
        raise PermissionError("synthetic read denial")

    result = DetectFileTypeCommand(
        magic_provider=None,
        open_file=refuse_open,
    ).execute(target)

    assert result["success"] is False
    assert result["error_code"] == "file_read_failed"
    assert result["error"] == "PermissionError: synthetic read denial"
