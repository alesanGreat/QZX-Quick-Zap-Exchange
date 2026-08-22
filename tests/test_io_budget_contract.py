"""Structural I/O budgets for bounded analysis and streaming full scans."""

from __future__ import annotations

from dataclasses import dataclass, field

from qzx.commands.file.count_lines import CountLinesCommand
from qzx.commands.file.detect_file_type import DetectFileTypeCommand
from qzx.commands.file.is_file_empty import IsFileEmptyCommand


@dataclass
class ReadEvidence:
    requested_sizes: list[int] = field(default_factory=list)
    returned_sizes: list[int] = field(default_factory=list)
    seek_calls: list[tuple[int, int]] = field(default_factory=list)
    open_count: int = 0


class RecordingHandle:
    def __init__(self, handle, evidence):
        self._handle = handle
        self._evidence = evidence

    def __enter__(self):
        self._handle.__enter__()
        return self

    def __exit__(self, exc_type, exc, traceback):
        return self._handle.__exit__(exc_type, exc, traceback)

    def read(self, size=-1):
        self._evidence.requested_sizes.append(size)
        data = self._handle.read(size)
        self._evidence.returned_sizes.append(len(data))
        return data

    def seek(self, offset, whence=0):
        self._evidence.seek_calls.append((offset, whence))
        return self._handle.seek(offset, whence)

    def __getattr__(self, name):
        return getattr(self._handle, name)


class RecordingOpen:
    def __init__(self):
        self.evidence = ReadEvidence()

    def __call__(self, path, mode):
        self.evidence.open_count += 1
        return RecordingHandle(open(path, mode), self.evidence)


def test_type_detection_reads_one_fixed_budget_from_a_one_gibibyte_file(tmp_path):
    target = tmp_path / "huge-sparse.bin"
    with target.open("wb") as file_handle:
        file_handle.write(b"QZX bounded sample\n")
        file_handle.truncate(1024**3)
    recorder = RecordingOpen()

    result = DetectFileTypeCommand(
        magic_provider=None,
        open_file=recorder,
    ).execute(target, detailed_info=True, sample_size=64 * 1024)

    assert result["success"] is True
    evidence = recorder.evidence
    assert evidence.open_count == 1
    assert -1 not in evidence.requested_sizes
    assert sum(evidence.returned_sizes) == 64 * 1024
    assert max(evidence.requested_sizes) <= 64 * 1024
    assert len(evidence.seek_calls) == 3
    assert result["details"]["sampling"]["analyzed_bytes"] == 64 * 1024
    assert result["details"]["sampling"]["full_file_analyzed"] is False


def test_count_lines_streams_fixed_chunks_and_reads_each_byte_once(tmp_path):
    target = tmp_path / "large-lines.txt"
    block = b"line\n" * 8192
    with target.open("wb") as file_handle:
        for _ in range(128):
            file_handle.write(block)
    recorder = RecordingOpen()

    result = CountLinesCommand(open_file=recorder).execute(
        target,
        encoding="utf-8",
    )

    assert result["success"] is True
    assert result["line_count"] == 8192 * 128
    evidence = recorder.evidence
    assert evidence.open_count == 1
    assert -1 not in evidence.requested_sizes
    assert set(evidence.requested_sizes) == {64 * 1024}
    assert sum(evidence.returned_sizes) == target.stat().st_size
    assert result["details"]["bytes_scanned"] == target.stat().st_size
    assert result["details"]["memory_policy"] == (
        "incremental_decoder_and_constant_line_state"
    )


def test_whitespace_emptiness_uses_bounded_sample_plus_one_streaming_pass(
    tmp_path,
):
    target = tmp_path / "large-whitespace.txt"
    block = b" \t\n\r" * 8192
    with target.open("wb") as file_handle:
        for _ in range(128):
            file_handle.write(block)
    recorder = RecordingOpen()

    result = IsFileEmptyCommand(open_file=recorder).execute(
        target,
        consider_whitespace=True,
    )

    assert result["success"] is True
    assert result["is_empty"] is True
    evidence = recorder.evidence
    assert evidence.open_count == 2
    assert -1 not in evidence.requested_sizes
    assert max(evidence.requested_sizes) <= 64 * 1024
    assert sum(evidence.returned_sizes) == (
        target.stat().st_size + 64 * 1024
    )
    assert result["details"]["sampling"]["analyzed_bytes"] == 64 * 1024
    assert result["details"]["whitespace_scan_bytes"] == target.stat().st_size
    assert result["details"]["full_content_scanned"] is True
