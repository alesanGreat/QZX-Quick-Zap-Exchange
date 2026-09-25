"""Decision workflow for countLines."""

from __future__ import annotations

from qzx.core.file_content_analysis import (
    DEFAULT_TYPE_SAMPLE_SIZE,
    FileChangedDuringReadError,
    analyze_binary_content,
    normalize_boolean,
    read_distributed_sample,
    validate_regular_file,
)


def count_file_lines(command, file_path, encoding="auto", follow_symlinks=False):
    """Return the stable public countLines result."""
    follow_links, error = normalize_boolean(
        follow_symlinks,
        field="follow_symlinks",
        command_base=command,
    )
    if error is not None:
        return error

    normalized_encoding, error = command._normalize_encoding(encoding)
    if error is not None:
        return error

    target, error = validate_regular_file(
        file_path,
        follow_symlinks=follow_links,
    )
    if error is not None:
        return error

    detection_details, normalized_encoding, failure = _resolve_encoding(
        command,
        target,
        normalized_encoding,
    )
    if failure is not None:
        return failure

    scan, failure = _run_scan(command, target, normalized_encoding)
    if failure is not None:
        return failure

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

    return _success_result(target, normalized_encoding, scan, details)


def _resolve_encoding(command, target, normalized_encoding):
    if normalized_encoding != "auto":
        return None, normalized_encoding, None
    if target.file_size == 0:
        return _empty_file_detection(), "utf-8", None

    sample, failure = _sample_for_encoding(command, target)
    if failure is not None:
        return None, None, failure
    return _detected_encoding_result(command, target, sample)


def _sample_for_encoding(command, target):
    try:
        sample = read_distributed_sample(
            target,
            DEFAULT_TYPE_SAMPLE_SIZE,
            open_file=command._open_file,
        )
        return sample, None
    except FileChangedDuringReadError as exc:
        return None, command._changed_result(
            target,
            exc,
            phase="sampling",
        )
    except OSError as exc:
        return None, command._read_failure(
            target,
            exc,
            phase="sampling",
        )


def _detected_encoding_result(command, target, sample):
    binary_analysis = analyze_binary_content(
        sample,
        threshold=10.0,
        path=target.analyzed_path,
        detect_encoding=command._detect_encoding,
    )
    details = {
        "sampling": sample.evidence(),
        "binary_analysis": binary_analysis,
    }
    detected = binary_analysis.get("encoding_detected")
    if detected is not None:
        return details, detected, None
    return details, None, _encoding_not_detected(target, details)


def _encoding_not_detected(target, detection_details):
    return {
        "success": False,
        "error_code": "text_encoding_not_detected",
        "error": (
            "QZX could not establish a strict text encoding for the requested file."
        ),
        "message": (
            "Line counting requires decodable text; provide an explicit encoding "
            "only after reviewing the file contents."
        ),
        "file_path": str(target.absolute_path),
        "analyzed_path": str(target.analyzed_path),
        "details": {
            "target": target.evidence(),
            **detection_details,
        },
    }


def _empty_file_detection():
    return {
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


def _run_scan(command, target, normalized_encoding):
    try:
        return command._count_stream(target, normalized_encoding), None
    except FileChangedDuringReadError as exc:
        return None, command._changed_result(target, exc, phase="line_scan")
    except LookupError as exc:
        return None, {
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
        return None, {
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
        return None, command._read_failure(target, exc, phase="line_scan")


def _success_result(target, encoding, scan, details):
    return {
        "success": True,
        "message": (
            f"Counted {scan['line_count']} logical line"
            f"{'s' if scan['line_count'] != 1 else ''} in "
            f"'{target.absolute_path}' using {encoding} streaming."
        ),
        "file_path": str(target.absolute_path),
        "analyzed_path": str(target.analyzed_path),
        "line_count": scan["line_count"],
        "non_blank_line_count": scan["non_blank_line_count"],
        "blank_line_count": scan["blank_line_count"],
        "empty_line_count": scan["empty_line_count"],
        "whitespace_only_line_count": scan["whitespace_only_line_count"],
        "encoding": encoding,
        "details": details,
    }
