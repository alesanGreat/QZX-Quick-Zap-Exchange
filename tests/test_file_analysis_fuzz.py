"""Deterministic fuzz/property tests for streaming text and bounded sampling."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
import random
import re

from qzx.commands.file.count_lines import CountLinesCommand
from qzx.core.file_content_analysis import (
    FileTarget,
    SampleSegment,
    _try_decode,
    analyze_binary_content,
    read_distributed_sample,
    regular_file_fingerprint,
)


FUZZ_SEED = 0x515A58
LINE_BREAK_PATTERN = re.compile(
    r"\r\n|[\n\v\f\r\x1c\x1d\x1e\x85\u2028\u2029]"
)
LINE_BREAK_NAMES = {
    "\r\n": "crlf",
    "\r": "cr",
    "\n": "lf",
    "\v": "vertical_tab",
    "\f": "form_feed",
    "\x1c": "file_separator",
    "\x1d": "group_separator",
    "\x1e": "record_separator",
    "\x85": "next_line",
    "\u2028": "line_separator",
    "\u2029": "paragraph_separator",
}
TEXT_ALPHABET = (
    list("abcXYZ0123")
    + [" ", "\t", "\u00a0", "\u2003"]
    + list(LINE_BREAK_NAMES)
    + ["é", "€", "α", "中", "🙂"]
)


class VariableChunkCountLines(CountLinesCommand):
    def __init__(self, chunk_size):
        super().__init__()
        self._CHUNK_SIZE = chunk_size


def _reference_line_evidence(text):
    if text.startswith("\ufeff"):
        text = text[1:]
    lines = text.splitlines()
    matches = list(LINE_BREAK_PATTERN.finditer(text))
    newline_counts = Counter(
        LINE_BREAK_NAMES[match.group(0)] for match in matches
    )
    return {
        "line_count": len(lines),
        "non_blank_line_count": sum(
            any(not character.isspace() for character in line) for line in lines
        ),
        "blank_line_count": sum(
            all(character.isspace() for character in line) for line in lines
        ),
        "empty_line_count": sum(line == "" for line in lines),
        "whitespace_only_line_count": sum(
            bool(line) and all(character.isspace() for character in line)
            for line in lines
        ),
        "max_line_length_characters": max(map(len, lines), default=0),
        "newline_sequence_count": len(matches),
        "newline_counts": newline_counts,
        "ends_with_line_break": bool(
            text and any(text.endswith(sequence) for sequence in LINE_BREAK_NAMES)
        ),
    }


def test_count_lines_matches_python_unicode_splitlines_across_fuzzed_chunks(
    tmp_path,
):
    random_source = random.Random(FUZZ_SEED)
    target = tmp_path / "fuzzed-lines.txt"

    for case_index in range(300):
        length = random_source.randrange(0, 500)
        text = "".join(random_source.choice(TEXT_ALPHABET) for _ in range(length))
        if random_source.randrange(5) == 0:
            text = "\ufeff" + text
        target.write_bytes(text.encode("utf-8"))
        chunk_size = random_source.randrange(1, 18)

        result = VariableChunkCountLines(chunk_size).execute(
            target,
            encoding="utf-8",
        )
        expected = _reference_line_evidence(text)

        assert result["success"] is True, (case_index, chunk_size, text, result)
        for key in (
            "line_count",
            "non_blank_line_count",
            "blank_line_count",
            "empty_line_count",
            "whitespace_only_line_count",
        ):
            assert result[key] == expected[key], (
                case_index,
                chunk_size,
                key,
                text,
                result,
                expected,
            )
        details = result["details"]
        assert details["max_line_length_characters"] == expected[
            "max_line_length_characters"
        ]
        assert details["newline_sequence_count"] == expected[
            "newline_sequence_count"
        ]
        assert details["ends_with_line_break"] is expected[
            "ends_with_line_break"
        ]
        for name in LINE_BREAK_NAMES.values():
            assert details["newline_counts"][name] == expected[
                "newline_counts"
            ].get(name, 0)


def test_incremental_utf8_probe_accepts_only_an_incomplete_tail():
    for character in ("é", "€", "🙂"):
        encoded = character.encode("utf-8")
        for missing_tail_bytes in range(1, len(encoded)):
            truncated = b"ASCII prefix " + encoded[:-missing_tail_bytes]
            assert _try_decode(
                truncated,
                "utf-8",
                allow_incomplete_tail=True,
            ) is not None
            assert _try_decode(truncated, "utf-8") is None

    assert _try_decode(
        b"ASCII\xffstill-invalid",
        "utf-8",
        allow_incomplete_tail=True,
    ) is None
    assert _try_decode(
        b"\x80orphan-continuation",
        "utf-8",
        allow_incomplete_tail=True,
    ) is None


class NoJoinSample:
    def __init__(self, *segments):
        self.segments = tuple(segments)

    @property
    def head(self):
        return self.segments[0].data if self.segments else b""

    @property
    def analyzed_bytes(self):
        return sum(len(segment.data) for segment in self.segments)

    @property
    def data(self):
        raise AssertionError("binary analysis must not concatenate sample segments")


def test_binary_analysis_counts_segments_without_materializing_a_joined_copy():
    text_sample = NoJoinSample(
        SampleSegment(offset=0, requested_bytes=5, data=b"hello"),
        SampleSegment(offset=100, requested_bytes=6, data=b" world"),
    )
    binary_sample = NoJoinSample(
        SampleSegment(
            offset=0,
            requested_bytes=8,
            data=b"\x89PNG\r\n\x1a\n",
        ),
        SampleSegment(offset=100, requested_bytes=4, data=b"\x00" * 4),
    )

    text_result = analyze_binary_content(
        text_sample,
        threshold=10.0,
        path=Path("sample.txt"),
    )
    binary_result = analyze_binary_content(
        binary_sample,
        threshold=10.0,
        path=Path("sample.bin"),
    )

    assert text_result["is_binary"] is False
    assert text_result["sampled_byte_count"] == 11
    assert binary_result["is_binary"] is True
    assert binary_result["sampled_byte_count"] == 12
    assert binary_result["null_byte_count"] == 4


def _target_for(path: Path) -> FileTarget:
    absolute = path.absolute()
    fingerprint = regular_file_fingerprint(absolute)
    return FileTarget(
        requested_path=str(path),
        absolute_path=absolute,
        analyzed_path=absolute,
        file_size=fingerprint[0],
        followed_link=False,
        link_components=(),
        fingerprint=fingerprint,
    )


def test_distributed_sampling_obeys_one_budget_and_stays_inside_every_file(
    tmp_path,
):
    random_source = random.Random(FUZZ_SEED ^ 0xBAD5EED)
    target_path = tmp_path / "sample.bin"

    for _case_index in range(250):
        file_size = random_source.randrange(0, 20_000)
        budget = random_source.randrange(64, 4097)
        target_path.write_bytes(bytes(index % 251 for index in range(file_size)))

        target = _target_for(target_path)
        sample = read_distributed_sample(target, budget)

        assert sample.analyzed_bytes == min(file_size, budget)
        assert len(sample.data) == sample.analyzed_bytes
        assert sample.evidence()["short_read_detected"] is False
        assert sample.full_file_analyzed is (file_size <= budget)
        assert all(
            0 <= segment.offset <= file_size
            and segment.requested_bytes == len(segment.data)
            and segment.offset + len(segment.data) <= file_size
            for segment in sample.segments
        )
        if file_size > budget:
            assert sample.strategy == "distributed_start_middle_end"
            assert len(sample.segments) == 3
            assert sample.segments[0].offset == 0
            assert (
                sample.segments[-1].offset
                + sample.segments[-1].requested_bytes
                == file_size
            )
            assert all(
                left.offset + left.requested_bytes <= right.offset
                for left, right in zip(sample.segments, sample.segments[1:])
            )
        elif file_size:
            assert sample.strategy == "whole_file"
            assert len(sample.segments) == 1
        else:
            assert sample.strategy == "empty_file"
            assert sample.segments == ()
