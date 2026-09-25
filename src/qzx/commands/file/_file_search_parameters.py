"""Validated filters for filename/metadata search; no traversal or content reads."""

from __future__ import annotations

from dataclasses import dataclass
import datetime
import math
import re


class SearchParameterError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class FileSearchOptions:
    depth: int | None
    min_bytes: int | None
    max_bytes: int | None
    after_timestamp: float | None
    before_timestamp: float | None
    modified_after: str | None
    modified_before: str | None
    exclude: list[str]
    exclude_dirs: list[str]
    sort_by: str
    descending: bool
    limit: int | None


def search_options(recursive, min_size, max_size, modified_after, modified_before,
                   exclude, exclude_dirs, sort_by, descending, limit):
    normalized_sort = str(sort_by).strip().lower()
    options = FileSearchOptions(
        depth=parse_recursion(recursive), min_bytes=parse_size_limit(min_size, "min_size"),
        max_bytes=parse_size_limit(max_size, "max_size"),
        after_timestamp=parse_date_limit(modified_after, "modified_after"),
        before_timestamp=parse_date_limit(modified_before, "modified_before"),
        modified_after=modified_after, modified_before=modified_before,
        exclude=parse_patterns(exclude, "exclude"),
        exclude_dirs=parse_patterns(exclude_dirs, "exclude_dirs"),
        sort_by=normalized_sort, descending=parse_boolean(descending, "descending"),
        limit=parse_limit(limit),
    )
    _validate_ranges(options)
    if normalized_sort not in {"path", "name", "size", "modified"}:
        raise SearchParameterError(
            "invalid_sort", "sort_by must be one of: path, name, size, modified."
        )
    return options


def _validate_ranges(options):
    if options.min_bytes is not None and options.max_bytes is not None:
        if options.min_bytes > options.max_bytes:
            raise SearchParameterError(
                "invalid_size_range", "min_size cannot be greater than max_size."
            )
    if options.after_timestamp is not None and options.before_timestamp is not None:
        if options.after_timestamp >= options.before_timestamp:
            raise SearchParameterError(
                "invalid_date_range", "modified_after must be earlier than modified_before."
            )


def parse_recursion(value):
    if value is None or value is True:
        return None
    if value is False:
        return 0
    if isinstance(value, int):
        if value < 0:
            raise ValueError("recursive depth cannot be negative.")
        return value
    message = "recursive must be -r, false, or a non-negative depth such as -r2."
    if not isinstance(value, str):
        raise ValueError(message)
    normalized = value.strip().lower()
    if normalized in {"-r", "--recursive", "true", "yes", "unlimited"}:
        return None
    if normalized in {"false", "no", "none", "0", "off"}:
        return 0
    match = re.fullmatch(r"(?:-r|--recursive)(\d+)", normalized)
    if match:
        return int(match.group(1))
    if normalized.isdigit():
        return int(normalized)
    raise ValueError(message)


def parse_size_limit(value, name):
    if value is None or value == "":
        return None
    message = f"{name} must be a finite, non-negative number or size such as 10MiB."
    if isinstance(value, bool):
        raise ValueError(message)
    if isinstance(value, int):
        if value < 0:
            raise ValueError(message)
        return value
    if isinstance(value, float):
        return _size_integer(value, message)
    if not isinstance(value, str):
        raise ValueError(message)
    match = re.fullmatch(
        r"\s*(\d+(?:\.\d+)?)\s*(B|KB|KIB|MB|MIB|GB|GIB|TB|TIB)?\s*", value, re.IGNORECASE
    )
    if not match:
        raise ValueError(message)
    multipliers = {
        "B": 1, "KB": 1024, "KIB": 1024, "MB": 1024**2, "MIB": 1024**2,
        "GB": 1024**3, "GIB": 1024**3, "TB": 1024**4, "TIB": 1024**4,
    }
    number = float(match.group(1)) * multipliers[(match.group(2) or "B").upper()]
    return _size_integer(number, message)


def _size_integer(number, message):
    if not math.isfinite(number) or number < 0:
        raise ValueError(message)
    return int(number)


def parse_date_limit(value, name):
    if value is None or value == "":
        return None
    message = f"{name} must use YYYY-MM-DD, today, or yesterday."
    if not isinstance(value, str):
        raise ValueError(message)
    normalized = value.strip().lower()
    today = datetime.datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
    if normalized == "today":
        return today.timestamp()
    if normalized == "yesterday":
        return (today - datetime.timedelta(days=1)).timestamp()
    try:
        parsed = datetime.datetime.strptime(normalized, "%Y-%m-%d")
        return parsed.astimezone().timestamp()
    except (ValueError, OSError, OverflowError) as exc:
        raise ValueError(message) from exc


def parse_patterns(value, name):
    if value is None or value == "":
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, (list, tuple)) and all(isinstance(item, str) for item in value):
        return [item.strip() for item in value if item.strip()]
    raise ValueError(f"{name} must be a comma-separated list of globs.")


def parse_boolean(value, name):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "1", "on"}:
            return True
        if normalized in {"false", "no", "0", "off"}:
            return False
    raise ValueError(f"{name} must be true or false.")


def parse_limit(value):
    if value is None or value == "":
        return None
    message = "limit must be a positive integer."
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError(message)
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(message) from exc
    if parsed <= 0:
        raise ValueError(message)
    return parsed
