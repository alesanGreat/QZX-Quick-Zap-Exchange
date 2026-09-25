"""Workflow orchestration for isFileBinary."""

from __future__ import annotations

from qzx.core.file_content_analysis import (
    FileChangedDuringReadError,
    DEFAULT_BINARY_SAMPLE_SIZE,
    analyze_binary_content,
    detect_builtin_type,
    normalize_binary_threshold,
    normalize_boolean,
    normalize_sample_size,
    read_distributed_sample,
    validate_regular_file,
)


def _read_sample(command, target, sample_budget):
    try:
        kwargs = (
            {"open_file": command._open_file}
            if command._open_file is not None
            else {}
        )
        return read_distributed_sample(target, sample_budget, **kwargs), None
    except FileChangedDuringReadError as exc:
        return None, {
            "success": False,
            "error_code": "file_changed_during_read",
            "error": f"{type(exc).__name__}: {exc}",
            "message": (
                "The file changed while QZX was reading its bounded sample, "
                "so no classification was published."
            ),
            "details": target.evidence(),
        }
    except OSError as exc:
        return None, {
            "success": False,
            "error_code": "file_read_failed",
            "error": f"{type(exc).__name__}: {exc}",
            "message": "QZX could not read the requested file sample.",
            "details": target.evidence(),
        }


def _success(command, target, sample, analysis):
    detected = detect_builtin_type(target.analyzed_path, sample, analysis)
    kind = "binary" if analysis["is_binary"] else "text"
    return {
        "success": True,
        "message": (
            f"File '{target.absolute_path}' is classified as {kind}; "
            f"{sample.analyzed_bytes} of {target.file_size} bytes were "
            f"analyzed using {sample.strategy}."
        ),
        "file_path": str(target.absolute_path),
        "analyzed_path": str(target.analyzed_path),
        "is_binary": analysis["is_binary"],
        "file_size": target.file_size,
        "file_size_readable": command._format_bytes(float(target.file_size)),
        "analyzed_bytes": sample.analyzed_bytes,
        "mime_type": detected.mime_type,
        "details": {
            "target": target.evidence(),
            "sampling": sample.evidence(),
            "binary_analysis": analysis,
            "detected_type": detected.evidence(),
        },
    }


def execute_file_binary(
    command,
    file_path,
    sample_size=DEFAULT_BINARY_SAMPLE_SIZE,
    binary_threshold=10.0,
    follow_symlinks=False,
):
    """Classify one regular file using bounded distributed sampling."""
    sample_budget, error = normalize_sample_size(
        sample_size, default=DEFAULT_BINARY_SAMPLE_SIZE
    )
    if error is not None:
        return error
    threshold, error = normalize_binary_threshold(binary_threshold)
    if error is not None:
        return error
    follow_links, error = normalize_boolean(
        follow_symlinks,
        field="follow_symlinks",
        command_base=command,
    )
    if error is not None:
        return error
    target, error = validate_regular_file(
        file_path, follow_symlinks=follow_links
    )
    if error is not None:
        return error
    sample, error = _read_sample(command, target, sample_budget)
    if error is not None:
        return error
    analysis = analyze_binary_content(
        sample,
        threshold=threshold,
        path=target.analyzed_path,
        detect_encoding=command._detect_encoding,
    )
    return _success(command, target, sample, analysis)
