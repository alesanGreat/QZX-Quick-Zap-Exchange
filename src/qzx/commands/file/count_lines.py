#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Count logical Unicode lines with bounded memory and stable file evidence."""

from __future__ import annotations

import codecs

from qzx.core.command_base import CommandBase
from qzx.core.file_content_analysis import (
    DEFAULT_TYPE_SAMPLE_SIZE,
    FileChangedDuringReadError,
    analyze_binary_content,
    normalize_boolean,
    read_distributed_sample,
    regular_file_fingerprint,
    validate_regular_file,
)


class CountLinesCommand(CommandBase):
    """Count text lines without loading the complete file into memory."""

    name = "countLines"
    description = (
        "Counts logical Unicode lines in a stable regular file using bounded-memory "
        "streaming and explicit newline evidence"
    )
    category = "file"
    _CHUNK_SIZE = 64 * 1024
    _UNICODE_LINE_BREAKS = {
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

    parameters = [
        {
            "name": "file_path",
            "description": "Path to the regular text file to count",
            "required": True,
            "type": "str",
        },
        {
            "name": "encoding",
            "description": (
                "Text encoding name, or 'auto' to use bounded content detection"
            ),
            "required": False,
            "default": "auto",
            "type": "str",
        },
        {
            "name": "follow_symlinks",
            "description": (
                "Follow reviewed symbolic-link or junction components to their "
                "resolved regular-file target"
            ),
            "required": False,
            "default": False,
            "type": "bool",
        },
    ]

    examples = [
        {
            "command": "qzx countLines source.py",
            "description": "Count source lines with automatic encoding detection",
        },
        {
            "command": "qzx countLines legacy.txt windows-1252",
            "description": "Count a file with an explicit legacy encoding",
        },
        {
            "command": "qzx countLines reviewed-link auto true",
            "description": "Count the resolved target of an explicitly reviewed link",
        },
    ]

    def __init__(self, *, open_file=None, detect_encoding=None):
        super().__init__()
        self._open_file = open_file or open
        self._detect_encoding = detect_encoding

    def execute(self, file_path, encoding="auto", follow_symlinks=False):
        follow_links, error = normalize_boolean(
            follow_symlinks,
            field="follow_symlinks",
            command_base=self,
        )
        if error is not None:
            return error
        normalized_encoding, error = self._normalize_encoding(encoding)
        if error is not None:
            return error

        target, error = validate_regular_file(
            file_path,
            follow_symlinks=follow_links,
        )
        if error is not None:
            return error

        detection_details = None
        if normalized_encoding == "auto" and target.file_size == 0:
            normalized_encoding = "utf-8"
            detection_details = {
                "sampling": {
                    "strategy": "empty_file",
                    "budget_bytes": DEFAULT_TYPE_SAMPLE_SIZE,
                    "analyzed_bytes": 0,
                    "full_file_analyzed": True,
                    "segments": [],
                    "short_read_detected": False,
                },
                "binary_analysis": {
                    "is_binary": False,
                    "detection_method": "empty_file",
                    "encoding_detected": None,
                },
            }
        elif normalized_encoding == "auto":
            try:
                sample = read_distributed_sample(
                    target,
                    DEFAULT_TYPE_SAMPLE_SIZE,
                    open_file=self._open_file,
                )
            except FileChangedDuringReadError as exc:
                return self._changed_result(target, exc, phase="sampling")
            except OSError as exc:
                return self._read_failure(target, exc, phase="sampling")
            binary_analysis = analyze_binary_content(
                sample,
                threshold=10.0,
                path=target.analyzed_path,
                detect_encoding=self._detect_encoding,
            )
            normalized_encoding = binary_analysis.get("encoding_detected")
            detection_details = {
                "sampling": sample.evidence(),
                "binary_analysis": binary_analysis,
            }
            if normalized_encoding is None:
                return {
                    "success": False,
                    "error_code": "text_encoding_not_detected",
                    "error": (
                        "QZX could not establish a strict text encoding for the "
                        "requested file."
                    ),
                    "message": (
                        "Line counting requires decodable text; provide an explicit "
                        "encoding only after reviewing the file contents."
                    ),
                    "file_path": str(target.absolute_path),
                    "analyzed_path": str(target.analyzed_path),
                    "details": {
                        "target": target.evidence(),
                        **detection_details,
                    },
                }

        try:
            scan = self._count_stream(target, normalized_encoding)
        except FileChangedDuringReadError as exc:
            return self._changed_result(target, exc, phase="line_scan")
        except LookupError as exc:
            return {
                "success": False,
                "error_code": "text_decoder_unavailable",
                "error": f"{type(exc).__name__}: {exc}",
                "message": (
                    f"QZX could not initialize text decoder '{normalized_encoding}'."
                ),
                "details": {
                    "target": target.evidence(),
                    "encoding": normalized_encoding,
                },
            }
        except UnicodeDecodeError as exc:
            return {
                "success": False,
                "error_code": "text_decode_failed",
                "error": f"{type(exc).__name__}: {exc}",
                "message": (
                    f"File '{target.absolute_path}' is not valid "
                    f"{normalized_encoding} text."
                ),
                "file_path": str(target.absolute_path),
                "analyzed_path": str(target.analyzed_path),
                "details": {
                    "target": target.evidence(),
                    "encoding": normalized_encoding,
                    "bytes_scanned_before_failure": getattr(
                        exc,
                        "qzx_bytes_scanned",
                        None,
                    ),
                },
            }
        except OSError as exc:
            return self._read_failure(target, exc, phase="line_scan")

        details = {
            "target": target.evidence(),
            "encoding": normalized_encoding,
            "encoding_source": (
                "content_detection" if detection_details is not None else "explicit"
            ),
            **scan,
        }
        if detection_details is not None:
            details.update(detection_details)

        return {
            "success": True,
            "message": (
                f"Counted {scan['line_count']} logical line"
                f"{'s' if scan['line_count'] != 1 else ''} in "
                f"'{target.absolute_path}' using {normalized_encoding} streaming."
            ),
            "file_path": str(target.absolute_path),
            "analyzed_path": str(target.analyzed_path),
            "line_count": scan["line_count"],
            "non_blank_line_count": scan["non_blank_line_count"],
            "blank_line_count": scan["blank_line_count"],
            "empty_line_count": scan["empty_line_count"],
            "whitespace_only_line_count": scan["whitespace_only_line_count"],
            "encoding": normalized_encoding,
            "details": details,
        }

    @staticmethod
    def _normalize_encoding(value):
        if not isinstance(value, str) or not value.strip():
            return None, {
                "success": False,
                "error_code": "invalid_encoding",
                "error": "encoding must be non-empty text.",
                "message": "Provide 'auto' or a valid Python codec name.",
            }
        normalized = value.strip()
        if normalized.casefold() == "auto":
            return "auto", None
        try:
            return codecs.lookup(normalized).name, None
        except LookupError as exc:
            return None, {
                "success": False,
                "error_code": "invalid_encoding",
                "error": f"{type(exc).__name__}: {exc}",
                "message": f"Encoding '{normalized}' is not available.",
            }

    def _count_stream(self, target, encoding):
        initial_fingerprint = regular_file_fingerprint(target.analyzed_path)
        if initial_fingerprint != target.fingerprint:
            raise FileChangedDuringReadError(
                "The file changed between validation and line scanning."
            )

        decoder = codecs.getincrementaldecoder(encoding)(errors="strict")
        state = {
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
                **{name: 0 for name in self._UNICODE_LINE_BREAKS.values()},
            },
        }

        with self._open_file(target.analyzed_path, "rb") as file_handle:
            while True:
                chunk = file_handle.read(self._CHUNK_SIZE)
                if not chunk:
                    break
                state["bytes_scanned"] += len(chunk)
                try:
                    decoded = decoder.decode(chunk, final=False)
                except UnicodeDecodeError as exc:
                    exc.qzx_bytes_scanned = state["bytes_scanned"]
                    raise
                self._consume_text(decoded, state)
            try:
                decoded = decoder.decode(b"", final=True)
            except UnicodeDecodeError as exc:
                exc.qzx_bytes_scanned = state["bytes_scanned"]
                raise
            self._consume_text(decoded, state)

        if state["pending_cr"]:
            state["newline_counts"]["cr"] += 1
            state["pending_cr"] = False
        if state["current_line_length"]:
            self._finish_line(state)
            state["ends_with_line_break"] = False

        final_fingerprint = regular_file_fingerprint(target.analyzed_path)
        if state["bytes_scanned"] != target.file_size:
            raise FileChangedDuringReadError(
                "The bytes scanned no longer match the validated file size."
            )
        if final_fingerprint != initial_fingerprint:
            raise FileChangedDuringReadError(
                "The file changed while logical lines were being counted."
            )

        state.pop("current_line_length")
        state.pop("current_line_has_non_whitespace")
        state.pop("pending_cr")
        state.pop("at_text_start")
        state["full_content_scanned"] = True
        state["memory_policy"] = "incremental_decoder_and_constant_line_state"
        state["newline_sequence_count"] = sum(state["newline_counts"].values())
        return state

    def _consume_text(self, text, state):
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
                self._finish_line(state)
                state["pending_cr"] = True
                state["ends_with_line_break"] = True
                continue

            newline_name = self._UNICODE_LINE_BREAKS.get(character)
            if newline_name is not None:
                self._finish_line(state)
                state["newline_counts"][newline_name] += 1
                state["ends_with_line_break"] = True
                continue

            state["current_line_length"] += 1
            if not character.isspace():
                state["current_line_has_non_whitespace"] = True
            state["ends_with_line_break"] = False

    @staticmethod
    def _finish_line(state):
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

    @staticmethod
    def _changed_result(target, error, *, phase):
        return {
            "success": False,
            "error_code": "file_changed_during_read",
            "error": f"{type(error).__name__}: {error}",
            "message": (
                "The file changed while QZX was counting lines, so no count was "
                "published."
            ),
            "file_path": str(target.absolute_path),
            "analyzed_path": str(target.analyzed_path),
            "details": {
                "target": target.evidence(),
                "phase": phase,
            },
        }

    @staticmethod
    def _read_failure(target, error, *, phase):
        return {
            "success": False,
            "error_code": "file_read_failed",
            "error": f"{type(error).__name__}: {error}",
            "message": "QZX could not read the requested file while counting lines.",
            "file_path": str(target.absolute_path),
            "analyzed_path": str(target.analyzed_path),
            "details": {
                "target": target.evidence(),
                "phase": phase,
            },
        }
