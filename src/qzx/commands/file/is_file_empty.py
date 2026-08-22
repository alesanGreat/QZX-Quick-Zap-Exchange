#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Inspect zero-byte and whitespace-only file emptiness with bounded memory."""

from __future__ import annotations

import codecs
import os

from qzx.core.command_base import CommandBase
from qzx.core.file_content_analysis import (
    DEFAULT_TYPE_SAMPLE_SIZE,
    FileChangedDuringReadError,
    analyze_binary_content,
    normalize_boolean,
    read_distributed_sample,
    validate_regular_file,
)


class IsFileEmptyCommand(CommandBase):
    """Check one regular file without loading its complete content into memory."""

    name = "isFileEmpty"
    description = (
        "Checks zero-byte or whitespace-only file emptiness with streaming text "
        "decoding and no symbolic-link traversal by default"
    )
    category = "file"
    _byte_units = ("B", "KB", "MB", "GB", "TB", "PB")
    _STREAM_CHUNK_SIZE = 64 * 1024

    parameters = [
        {
            "name": "file_path",
            "description": "Path to the regular file to inspect",
            "required": True,
            "type": "str",
        },
        {
            "name": "consider_whitespace",
            "description": (
                "Treat a fully decoded file containing only Unicode whitespace "
                "as empty"
            ),
            "required": False,
            "default": False,
            "type": "bool",
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
            "command": "qzx isFileEmpty /path/to/file.txt",
            "description": "Check whether a regular file has zero bytes",
        },
        {
            "command": "qzx isFileEmpty /path/to/file.txt true",
            "description": "Also treat Unicode whitespace-only text as empty",
        },
        {
            "command": "qzx isFileEmpty reviewed-link true true",
            "description": "Inspect an explicitly reviewed linked file target",
        },
    ]

    def __init__(self, *, open_file=None, detect_encoding=None):
        super().__init__()
        self._open_file = open_file or open
        self._detect_encoding = detect_encoding

    def execute(
        self,
        file_path,
        consider_whitespace=False,
        follow_symlinks=False,
    ):
        """Return a stable emptiness decision with its exact proof basis."""
        consider_whitespace, error = normalize_boolean(
            consider_whitespace,
            field="consider_whitespace",
            command_base=self,
        )
        if error is not None:
            return error
        follow_links, error = normalize_boolean(
            follow_symlinks,
            field="follow_symlinks",
            command_base=self,
        )
        if error is not None:
            return error

        target, error = validate_regular_file(
            file_path,
            follow_symlinks=follow_links,
        )
        if error is not None:
            return error

        if target.file_size == 0:
            return self._result(
                target,
                consider_whitespace=consider_whitespace,
                is_empty=True,
                is_whitespace_only=(True if consider_whitespace else None),
                message=(
                    f"File '{target.absolute_path}' is completely empty (0 bytes)."
                ),
                details={
                    "emptiness_basis": "zero_bytes",
                    "full_content_scanned": True,
                    "whitespace_scan_bytes": 0,
                    "whitespace_scan_status": "not_needed",
                },
            )

        if not consider_whitespace:
            return self._result(
                target,
                consider_whitespace=False,
                is_empty=False,
                is_whitespace_only=None,
                message=(
                    f"File '{target.absolute_path}' is not empty "
                    f"({target.file_size} bytes)."
                ),
                details={
                    "emptiness_basis": "nonzero_size",
                    "full_content_scanned": False,
                    "whitespace_scan_bytes": 0,
                    "whitespace_scan_status": "disabled",
                },
            )

        try:
            sample = read_distributed_sample(
                target,
                DEFAULT_TYPE_SAMPLE_SIZE,
                open_file=self._open_file,
            )
        except FileChangedDuringReadError as exc:
            return self._changed_file_result(
                target,
                0,
                f"{type(exc).__name__}: {exc}",
                phase="sampling",
            )
        except OSError as exc:
            return self._read_failure(target, exc, phase="sampling")

        binary_analysis = analyze_binary_content(
            sample,
            threshold=10.0,
            path=target.analyzed_path,
            detect_encoding=self._detect_encoding,
        )
        sample_details = {
            "sampling": sample.evidence(),
            "binary_analysis": binary_analysis,
        }
        if binary_analysis["detection_method"] == "content_signature":
            return self._result(
                target,
                consider_whitespace=True,
                is_empty=False,
                is_whitespace_only=False,
                message=(
                    f"File '{target.absolute_path}' is not empty; a binary content "
                    f"signature was detected in {target.file_size} bytes."
                ),
                details={
                    **sample_details,
                    "emptiness_basis": "binary_content_signature",
                    "full_content_scanned": False,
                    "whitespace_scan_bytes": 0,
                    "whitespace_scan_status": "not_text",
                },
            )

        encoding = binary_analysis.get("encoding_detected")
        if encoding is None:
            return self._result(
                target,
                consider_whitespace=True,
                is_empty=False,
                is_whitespace_only=False,
                message=(
                    f"File '{target.absolute_path}' is not empty; its nonzero "
                    "content could not be decoded as supported text."
                ),
                details={
                    **sample_details,
                    "emptiness_basis": "encoding_unavailable",
                    "full_content_scanned": False,
                    "whitespace_scan_bytes": 0,
                    "whitespace_scan_status": "not_decodable",
                },
            )

        scan = self._scan_unicode_whitespace(target, encoding)
        if not scan["success"]:
            return {
                "success": False,
                "error_code": scan["error_code"],
                "error": scan["error"],
                "message": scan["message"],
                "file_path": str(target.absolute_path),
                "analyzed_path": str(target.analyzed_path),
                "details": {
                    "target": target.evidence(),
                    **sample_details,
                    **scan["details"],
                },
            }

        if scan["is_whitespace_only"]:
            message = (
                f"File '{target.absolute_path}' contains only Unicode whitespace "
                f"({target.file_size} bytes)."
            )
            basis = "unicode_whitespace_only"
        elif scan["status"] == "decode_error":
            message = (
                f"File '{target.absolute_path}' is not empty; decoding failed "
                "before a whitespace-only proof could be established."
            )
            basis = "decode_error"
        else:
            message = (
                f"File '{target.absolute_path}' is not empty; non-whitespace "
                f"text was found after scanning {scan['bytes_scanned']} bytes."
            )
            basis = "non_whitespace_content"

        return self._result(
            target,
            consider_whitespace=True,
            is_empty=scan["is_whitespace_only"],
            is_whitespace_only=scan["is_whitespace_only"],
            message=message,
            details={
                **sample_details,
                "emptiness_basis": basis,
                "text_encoding": encoding,
                "full_content_scanned": scan["full_content_scanned"],
                "whitespace_scan_bytes": scan["bytes_scanned"],
                "whitespace_scan_status": scan["status"],
                "first_non_whitespace_codepoint": scan.get(
                    "first_non_whitespace_codepoint"
                ),
                "decode_error": scan.get("decode_error"),
            },
        )

    def _scan_unicode_whitespace(self, target, encoding):
        try:
            decoder_factory = codecs.getincrementaldecoder(encoding)
        except LookupError as exc:
            return {
                "success": False,
                "error_code": "text_decoder_unavailable",
                "error": f"{type(exc).__name__}: {exc}",
                "message": (
                    f"QZX could not initialize the detected text decoder "
                    f"'{encoding}'."
                ),
                "details": {
                    "text_encoding": encoding,
                    "full_content_scanned": False,
                    "whitespace_scan_bytes": 0,
                },
            }

        bytes_scanned = 0
        at_text_start = True
        try:
            initial_fingerprint = self._path_fingerprint(target.analyzed_path)
            if initial_fingerprint[0] != target.file_size:
                return self._changed_file_result(
                    target,
                    bytes_scanned,
                    "The file size changed between path validation and opening.",
                )

            with self._open_file(target.analyzed_path, "rb") as file_handle:
                decoder = decoder_factory(errors="strict")
                while True:
                    chunk = file_handle.read(self._STREAM_CHUNK_SIZE)
                    if not chunk:
                        break
                    bytes_scanned += len(chunk)
                    try:
                        decoded = decoder.decode(chunk, final=False)
                    except UnicodeDecodeError as exc:
                        return {
                            "success": True,
                            "is_whitespace_only": False,
                            "status": "decode_error",
                            "bytes_scanned": bytes_scanned,
                            "full_content_scanned": False,
                            "decode_error": f"{type(exc).__name__}: {exc}",
                        }
                    non_whitespace, at_text_start = self._first_non_whitespace(
                        decoded,
                        at_text_start=at_text_start,
                    )
                    if non_whitespace is not None:
                        return {
                            "success": True,
                            "is_whitespace_only": False,
                            "status": "non_whitespace_found",
                            "bytes_scanned": bytes_scanned,
                            "full_content_scanned": False,
                            "first_non_whitespace_codepoint": (
                                f"U+{ord(non_whitespace):04X}"
                            ),
                        }

                try:
                    decoded = decoder.decode(b"", final=True)
                except UnicodeDecodeError as exc:
                    return {
                        "success": True,
                        "is_whitespace_only": False,
                        "status": "decode_error",
                        "bytes_scanned": bytes_scanned,
                        "full_content_scanned": True,
                        "decode_error": f"{type(exc).__name__}: {exc}",
                    }
                non_whitespace, _at_text_start = self._first_non_whitespace(
                    decoded,
                    at_text_start=at_text_start,
                )
                if non_whitespace is not None:
                    return {
                        "success": True,
                        "is_whitespace_only": False,
                        "status": "non_whitespace_found",
                        "bytes_scanned": bytes_scanned,
                        "full_content_scanned": True,
                        "first_non_whitespace_codepoint": (
                            f"U+{ord(non_whitespace):04X}"
                        ),
                    }

            final_fingerprint = self._path_fingerprint(target.analyzed_path)
        except OSError as exc:
            return {
                "success": False,
                "error_code": "file_read_failed",
                "error": f"{type(exc).__name__}: {exc}",
                "message": "QZX could not complete the whitespace scan.",
                "details": {
                    "phase": "whitespace_scan",
                    "text_encoding": encoding,
                    "full_content_scanned": False,
                    "whitespace_scan_bytes": bytes_scanned,
                },
            }

        if bytes_scanned != target.file_size:
            return self._changed_file_result(
                target,
                bytes_scanned,
                "The number of bytes read no longer matches the validated size.",
            )
        if initial_fingerprint != final_fingerprint:
            return self._changed_file_result(
                target,
                bytes_scanned,
                "The file path changed while the whitespace scan was running.",
            )
        return {
            "success": True,
            "is_whitespace_only": True,
            "status": "whitespace_only",
            "bytes_scanned": bytes_scanned,
            "full_content_scanned": True,
        }

    @staticmethod
    def _first_non_whitespace(text, *, at_text_start):
        for character in text:
            if at_text_start:
                at_text_start = False
                if character == "\ufeff":
                    continue
            if not character.isspace():
                return character, at_text_start
        return None, at_text_start

    @staticmethod
    def _path_fingerprint(path):
        file_stat = os.stat(path, follow_symlinks=True)
        return (
            file_stat.st_size,
            getattr(file_stat, "st_mtime_ns", None),
            file_stat.st_dev,
            file_stat.st_ino,
        )

    @staticmethod
    def _changed_file_result(
        target,
        bytes_scanned,
        reason,
        *,
        phase="whitespace_scan",
    ):
        return {
            "success": False,
            "error_code": "file_changed_during_read",
            "error": reason,
            "message": (
                f"File '{target.absolute_path}' changed while QZX was reading it, "
                "so no emptiness conclusion was published."
            ),
            "file_path": str(target.absolute_path),
            "analyzed_path": str(target.analyzed_path),
            "details": {
                "target": target.evidence(),
                "phase": phase,
                "validated_size": target.file_size,
                "whitespace_scan_bytes": bytes_scanned,
                "full_content_scanned": False,
            },
        }

    @staticmethod
    def _read_failure(target, error, *, phase):
        return {
            "success": False,
            "error_code": "file_read_failed",
            "error": f"{type(error).__name__}: {error}",
            "message": "QZX could not read the requested file.",
            "file_path": str(target.absolute_path),
            "analyzed_path": str(target.analyzed_path),
            "details": {
                "target": target.evidence(),
                "phase": phase,
            },
        }

    def _result(
        self,
        target,
        *,
        consider_whitespace,
        is_empty,
        is_whitespace_only,
        message,
        details,
    ):
        result = {
            "success": True,
            "message": message,
            "file_path": str(target.absolute_path),
            "analyzed_path": str(target.analyzed_path),
            "is_empty": is_empty,
            "file_size": target.file_size,
            "file_size_readable": self._format_bytes(float(target.file_size)),
            "consider_whitespace": consider_whitespace,
            "details": {
                "target": target.evidence(),
                **details,
            },
        }
        if consider_whitespace:
            result["is_whitespace_only"] = is_whitespace_only
        return result
