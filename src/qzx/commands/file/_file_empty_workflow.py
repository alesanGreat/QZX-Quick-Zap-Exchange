"""Decision workflow for isFileEmpty."""

from __future__ import annotations

from qzx.core.file_content_analysis import (
    DEFAULT_TYPE_SAMPLE_SIZE,
    FileChangedDuringReadError,
    analyze_binary_content,
    normalize_boolean,
    read_distributed_sample,
    validate_regular_file,
)


def inspect_file_emptiness(
    command,
    file_path,
    consider_whitespace=False,
    follow_symlinks=False,
):
    """Return the public isFileEmpty result through command compatibility hooks."""
    consider_whitespace, follow_links, error = _normalize_request(
        command,
        consider_whitespace,
        follow_symlinks,
    )
    if error is not None:
        return error

    target, error = validate_regular_file(
        file_path,
        follow_symlinks=follow_links,
    )
    if error is not None:
        return error

    size_result = _size_decision(command, target, consider_whitespace)
    if size_result is not None:
        return size_result

    sample_details, encoding, terminal = _sample_decision(command, target)
    if terminal is not None:
        return terminal
    return _whitespace_decision(
        command,
        target,
        encoding,
        sample_details,
    )


def _normalize_request(command, consider_whitespace, follow_symlinks):
    consider_whitespace, error = normalize_boolean(
        consider_whitespace,
        field="consider_whitespace",
        command_base=command,
    )
    if error is not None:
        return None, None, error
    follow_links, error = normalize_boolean(
        follow_symlinks,
        field="follow_symlinks",
        command_base=command,
    )
    return consider_whitespace, follow_links, error


def _size_decision(command, target, consider_whitespace):
    if target.file_size == 0:
        return command._result(
            target,
            consider_whitespace=consider_whitespace,
            is_empty=True,
            is_whitespace_only=(True if consider_whitespace else None),
            message=f"File '{target.absolute_path}' is completely empty (0 bytes).",
            details={
                "emptiness_basis": "zero_bytes",
                "full_content_scanned": True,
                "whitespace_scan_bytes": 0,
                "whitespace_scan_status": "not_needed",
            },
        )
    if consider_whitespace:
        return None
    return command._result(
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


def _sample_decision(command, target):
    try:
        sample = read_distributed_sample(
            target,
            DEFAULT_TYPE_SAMPLE_SIZE,
            open_file=command._open_file,
        )
    except FileChangedDuringReadError as exc:
        return None, None, command._changed_file_result(
            target,
            0,
            f"{type(exc).__name__}: {exc}",
            phase="sampling",
        )
    except OSError as exc:
        return None, None, command._read_failure(target, exc, phase="sampling")

    analysis = analyze_binary_content(
        sample,
        threshold=10.0,
        path=target.analyzed_path,
        detect_encoding=command._detect_encoding,
    )
    details = {"sampling": sample.evidence(), "binary_analysis": analysis}
    terminal = _binary_or_encoding_result(command, target, analysis, details)
    return details, analysis.get("encoding_detected"), terminal


def _binary_or_encoding_result(command, target, analysis, sample_details):
    if analysis["detection_method"] == "content_signature":
        return command._result(
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
    if analysis.get("encoding_detected") is not None:
        return None
    return command._result(
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


def _whitespace_decision(command, target, encoding, sample_details):
    scan = command._scan_unicode_whitespace(target, encoding)
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

    message, basis = _scan_message_and_basis(target, scan)
    return command._result(
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


def _scan_message_and_basis(target, scan):
    if scan["is_whitespace_only"]:
        return (
            f"File '{target.absolute_path}' contains only Unicode whitespace "
            f"({target.file_size} bytes).",
            "unicode_whitespace_only",
        )
    if scan["status"] == "decode_error":
        return (
            f"File '{target.absolute_path}' is not empty; decoding failed "
            "before a whitespace-only proof could be established.",
            "decode_error",
        )
    return (
        f"File '{target.absolute_path}' is not empty; non-whitespace text was "
        f"found after scanning {scan['bytes_scanned']} bytes.",
        "non_whitespace_content",
    )
