"""Strict, shared scope validation for read-only storage workflows."""

from __future__ import annotations

import math
import os
import stat


class StorageInputError(ValueError):
    """A user-correctable path or scope error, before filesystem traversal."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def storage_directory(value) -> str:
    """Resolve an explicitly requested directory without scanning its contents."""
    try:
        path = os.fspath(value)
        if not isinstance(path, str) or "\x00" in path:
            raise TypeError
        absolute = os.path.abspath(path or ".")
    except (TypeError, ValueError) as exc:
        raise StorageInputError("invalid_path", "Path must be a filesystem path.") from exc
    try:
        info = os.stat(absolute)
    except FileNotFoundError as exc:
        raise StorageInputError(
            "path_not_found", f"Path '{absolute}' does not exist."
        ) from exc
    except OSError as exc:
        raise StorageInputError(
            "path_unavailable", f"Cannot inspect directory '{absolute}': {exc}"
        ) from exc
    if not stat.S_ISDIR(info.st_mode):
        raise StorageInputError(
            "not_a_directory", f"'{absolute}' is not a directory."
        )
    return absolute


def bounded_integer(value, name: str, minimum: int, maximum: int) -> int:
    """Reject booleans and lossy float-to-int coercion as well as bad bounds."""
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError(f"{name} must be an integer.")
    try:
        number = int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer.") from exc
    if not minimum <= number <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}.")
    return number


def minimum_file_bytes(value) -> float:
    """Accept finite, non-negative KiB thresholds, including fractional KiB."""
    message = "min_size_kb must be a finite, non-negative number."
    if isinstance(value, bool):
        raise ValueError(message)
    try:
        result = float(value) * 1024
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError(message) from exc
    if not math.isfinite(result) or result < 0:
        raise ValueError(message)
    return result
