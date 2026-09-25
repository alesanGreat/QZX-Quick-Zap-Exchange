"""Bounded local file sampling for explainFileWithGemini."""

from __future__ import annotations

import hashlib


def prepare_gemini_sample(command, path, sample_size, max_file_size_bytes):
    """Read a stable bounded-size file and create a bounded text sample."""
    payload, failure = _stable_payload(command, path, max_file_size_bytes)
    if failure is not None:
        return failure

    content, encoding, failure = _decoded_text(command, payload)
    if failure is not None:
        return failure

    sample, strategy, source_characters = _sample_text(
        content,
        sample_size,
    )
    return {
        "success": True,
        "sample": sample,
        "sample_strategy": strategy,
        "source_characters_shared": source_characters,
        "file_size_bytes": len(payload),
        "file_sha256": hashlib.sha256(payload).hexdigest(),
        "encoding": encoding,
    }


def _stable_payload(command, path, max_file_size_bytes):
    try:
        before = path.stat()
        if before.st_size > max_file_size_bytes:
            return None, command._failure(
                "file_too_large",
                "The file grew beyond the approved local read limit.",
                "Preview the current file again before sending content.",
            )
        payload = path.read_bytes()
        after = path.stat()
    except OSError as exc:
        return None, command._failure(
            "file_read_failed",
            "The selected file could not be read.",
            "Check permissions and retry the preview.",
            details={"cause": type(exc).__name__},
        )
    if (
        before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
    ):
        return None, command._failure(
            "file_changed_during_read",
            "The selected file changed while QZX was reading it.",
            "Wait for writes to finish, preview again, and then apply.",
        )
    if len(payload) > max_file_size_bytes:
        return None, command._failure(
            "file_too_large",
            "The file exceeded the approved local read limit.",
            "Preview the current file again before sending content.",
        )
    return payload, None


def _decoded_text(command, payload):
    try:
        content = payload.decode("utf-8")
        encoding = "utf-8"
    except UnicodeDecodeError:
        content = payload.decode("latin-1")
        encoding = "latin-1"
    if "\x00" in content:
        return None, None, command._failure(
            "binary_file_not_supported",
            "The selected file appears to contain binary data.",
            "Choose a text file or use a command designed for binary data.",
        )
    return content, encoding, None


def _sample_text(content, sample_size):
    if len(content) <= sample_size * 3:
        return content, "whole_file", len(content)

    middle_start = max(0, (len(content) - sample_size) // 2)
    beginning = content[:sample_size]
    middle = content[middle_start:middle_start + sample_size]
    end = content[-sample_size:]
    sample = (
        "--- BEGINNING OF FILE ---\n{}\n\n"
        "--- MIDDLE OF FILE ---\n{}\n\n"
        "--- END OF FILE ---\n{}"
    ).format(beginning, middle, end)
    source_characters = len(beginning) + len(middle) + len(end)
    return sample, "beginning_middle_end", source_characters
