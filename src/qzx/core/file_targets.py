"""Safe target validation and bounded sampling for file-content commands."""

from __future__ import annotations

from dataclasses import dataclass
import math
import os
from pathlib import Path
import stat


MIN_SAMPLE_SIZE = 64
MAX_SAMPLE_SIZE = 16 * 1024 * 1024
DEFAULT_BINARY_SAMPLE_SIZE = 8192
DEFAULT_TYPE_SAMPLE_SIZE = 64 * 1024


class FileChangedDuringReadError(OSError):
    """Raised when a validated regular file changes during bounded reading."""


class DirectoryChangedDuringScanError(OSError):
    """Raised when a validated directory changes during enumeration."""


@dataclass(frozen=True)
class FileTarget:
    requested_path: str
    absolute_path: Path
    analyzed_path: Path
    file_size: int
    followed_link: bool
    link_components: tuple[str, ...]
    fingerprint: tuple[int, int | None, int, int]

    def evidence(self):
        return {
            "requested_path": self.requested_path,
            "file_path": str(self.absolute_path),
            "analyzed_path": str(self.analyzed_path),
            "file_size": self.file_size,
            "followed_symlink": self.followed_link,
            "link_components": list(self.link_components),
            "fingerprint": _fingerprint_evidence(self.fingerprint),
        }


@dataclass(frozen=True)
class DirectoryTarget:
    requested_path: str
    absolute_path: Path
    analyzed_path: Path
    followed_link: bool
    link_components: tuple[str, ...]
    fingerprint: tuple[int, int | None, int, int]

    def evidence(self):
        return {
            "requested_path": self.requested_path,
            "directory_path": str(self.absolute_path),
            "analyzed_path": str(self.analyzed_path),
            "followed_symlink": self.followed_link,
            "link_components": list(self.link_components),
            "fingerprint": _fingerprint_evidence(self.fingerprint),
        }


def _fingerprint_evidence(fingerprint):
    return {
        "size_bytes": fingerprint[0],
        "modified_ns": fingerprint[1],
        "device": fingerprint[2],
        "inode": fingerprint[3],
    }


@dataclass(frozen=True)
class SampleSegment:
    offset: int
    requested_bytes: int
    data: bytes

    def evidence(self):
        return {
            "offset": self.offset,
            "requested_bytes": self.requested_bytes,
            "read_bytes": len(self.data),
        }


@dataclass(frozen=True)
class FileSample:
    file_size: int
    budget_bytes: int
    segments: tuple[SampleSegment, ...]

    @property
    def data(self):
        return b"".join(segment.data for segment in self.segments)

    @property
    def head(self):
        return self.segments[0].data if self.segments else b""

    @property
    def analyzed_bytes(self):
        return sum(len(segment.data) for segment in self.segments)

    @property
    def full_file_analyzed(self):
        return self.file_size <= self.budget_bytes

    @property
    def strategy(self):
        if self.file_size == 0:
            return "empty_file"
        if self.full_file_analyzed:
            return "whole_file"
        return "distributed_start_middle_end"

    def evidence(self):
        return {
            "strategy": self.strategy,
            "budget_bytes": self.budget_bytes,
            "analyzed_bytes": self.analyzed_bytes,
            "full_file_analyzed": self.full_file_analyzed,
            "segments": [segment.evidence() for segment in self.segments],
            "short_read_detected": any(
                len(segment.data) != segment.requested_bytes
                for segment in self.segments
            ),
        }


_PATH_KIND = {
    "file": {
        "field": "file_path",
        "operation": "analyze",
        "missing_code": "file_not_found",
        "inspection_code": "file_inspection_failed",
    },
    "directory": {
        "field": "directory_path",
        "operation": "inspect",
        "missing_code": "directory_not_found",
        "inspection_code": "directory_inspection_failed",
    },
}


def _path_components(path):
    current = Path(path.anchor)
    yield current
    for part in path.parts[1:]:
        current /= part
        yield current


def _is_link_or_junction(path):
    if os.path.islink(path):
        return True
    is_junction = getattr(os.path, "isjunction", None)
    return bool(is_junction is not None and is_junction(path))


def _entry_type(mode):
    for predicate, label in (
        (stat.S_ISREG, "regular_file"),
        (stat.S_ISDIR, "directory"),
        (stat.S_ISFIFO, "fifo"),
        (stat.S_ISSOCK, "socket"),
        (stat.S_ISCHR, "character_device"),
        (stat.S_ISBLK, "block_device"),
    ):
        if predicate(mode):
            return label
    return "special_entry"


def _path_failure(error_code, error, message, **details):
    return {
        "success": False,
        "error_code": error_code,
        "error": error,
        "message": message,
        "details": details,
    }


def _validated_path_text(value, kind):
    settings = _PATH_KIND[kind]
    field = settings["field"]
    operation = settings["operation"]
    try:
        raw_path = os.fspath(value)
    except TypeError:
        return None, _path_failure(
            "invalid_{}_path".format(kind),
            "{} must be text or a path-like object.".format(field),
            "Provide a valid {} path to {}.".format(kind, operation),
            requested_path=repr(value),
        )
    if not isinstance(raw_path, str):
        return None, _path_failure(
            "invalid_{}_path".format(kind),
            "{} must resolve to text, not raw bytes.".format(field),
            "Provide a text {} path to {}.".format(kind, operation),
            requested_path=repr(value),
        )
    if not raw_path:
        return None, _path_failure(
            "invalid_{}_path".format(kind),
            "{} must not be empty.".format(field),
            "Provide a non-empty {} path to {}.".format(kind, operation),
            requested_path=raw_path,
        )
    if "\x00" in raw_path:
        return None, _path_failure(
            "invalid_{}_path".format(kind),
            "{} must not contain NUL bytes.".format(field),
            "Provide a valid {} path to {}.".format(kind, operation),
            requested_path=raw_path,
        )
    return raw_path, None


def _inspected_target(raw_path, kind, follow_symlinks):
    settings = _PATH_KIND[kind]
    try:
        absolute = Path(os.path.abspath(os.path.expanduser(raw_path)))
        if not os.path.lexists(absolute):
            return None, _missing_path_failure(raw_path, absolute, kind)
        links = tuple(
            str(component)
            for component in _path_components(absolute)
            if _is_link_or_junction(component)
        )
        if links and not follow_symlinks:
            return None, _blocked_link_failure(raw_path, absolute, links, kind)
        analyzed = absolute.resolve(strict=True) if links else absolute
        target_stat = os.stat(analyzed, follow_symlinks=True)
        return (absolute, analyzed, links, target_stat), None
    except (OSError, RuntimeError, ValueError) as exc:
        return None, _path_failure(
            settings["inspection_code"],
            f"{type(exc).__name__}: {exc}",
            "QZX could not inspect the requested {} path.".format(kind),
            requested_path=raw_path,
        )


def _missing_path_failure(raw_path, absolute, kind):
    settings = _PATH_KIND[kind]
    return _path_failure(
        settings["missing_code"],
        "{} '{}' does not exist.".format(kind.capitalize(), absolute),
        "The requested {} was not found.".format(kind),
        requested_path=raw_path,
        **{"{}_path".format(kind): str(absolute)},
    )


def _blocked_link_failure(raw_path, absolute, links, kind):
    noun = "File analysis" if kind == "file" else "Directory inspection"
    return _path_failure(
        "symlink_path_blocked",
        "{} does not follow symbolic links or junctions by default.".format(noun),
        "Review the resolved target, then set follow_symlinks=true if that target is intentional.",
        requested_path=raw_path,
        **{
            "{}_path".format(kind): str(absolute),
            "blocked_component": links[0],
            "link_components": list(links),
        },
    )


def validate_regular_file(file_path, *, follow_symlinks=False):
    """Resolve one bounded regular-file target or return a QZX failure."""
    raw_path, error = _validated_path_text(file_path, "file")
    if error is not None:
        return None, error
    inspected, error = _inspected_target(raw_path, "file", follow_symlinks)
    if error is not None:
        return None, error
    absolute, analyzed, links, target_stat = inspected
    entry_type = _entry_type(target_stat.st_mode)
    if entry_type != "regular_file":
        return None, _path_failure(
            "not_a_regular_file",
            f"'{analyzed}' is {entry_type}, not a regular file.",
            "File-content analysis accepts only regular files.",
            requested_path=raw_path,
            file_path=str(absolute),
            analyzed_path=str(analyzed),
            entry_type=entry_type,
        )
    return FileTarget(
        requested_path=raw_path,
        absolute_path=absolute,
        analyzed_path=analyzed,
        file_size=target_stat.st_size,
        followed_link=bool(links),
        link_components=links,
        fingerprint=_stat_fingerprint(target_stat),
    ), None


def validate_directory(directory_path, *, follow_symlinks=False):
    """Resolve one real directory target or return a structured QZX failure."""
    raw_path, error = _validated_path_text(directory_path, "directory")
    if error is not None:
        return None, error
    inspected, error = _inspected_target(raw_path, "directory", follow_symlinks)
    if error is not None:
        return None, error
    absolute, analyzed, links, target_stat = inspected
    if not stat.S_ISDIR(target_stat.st_mode):
        return None, _path_failure(
            "not_a_directory",
            f"'{analyzed}' is not a directory.",
            "Directory inspection requires a directory target.",
            requested_path=raw_path,
            directory_path=str(absolute),
            analyzed_path=str(analyzed),
        )
    return DirectoryTarget(
        requested_path=raw_path,
        absolute_path=absolute,
        analyzed_path=analyzed,
        followed_link=bool(links),
        link_components=links,
        fingerprint=_stat_fingerprint(target_stat),
    ), None


def _stat_fingerprint(file_stat):
    return (
        file_stat.st_size,
        getattr(file_stat, "st_mtime_ns", None),
        file_stat.st_dev,
        file_stat.st_ino,
    )


def directory_fingerprint(path):
    directory_stat = os.stat(path, follow_symlinks=True)
    if not stat.S_ISDIR(directory_stat.st_mode):
        raise DirectoryChangedDuringScanError(
            f"Validated target '{path}' is no longer a directory."
        )
    return _stat_fingerprint(directory_stat)


def regular_file_fingerprint(path):
    file_stat = os.stat(path, follow_symlinks=True)
    if not stat.S_ISREG(file_stat.st_mode):
        raise FileChangedDuringReadError(
            f"Validated target '{path}' is no longer a regular file."
        )
    return _stat_fingerprint(file_stat)


def normalize_sample_size(value, *, default):
    candidate = default if value is None else value
    try:
        parsed = None if isinstance(candidate, bool) else int(candidate)
    except (TypeError, ValueError, OverflowError):
        parsed = None
    if parsed is not None and MIN_SAMPLE_SIZE <= parsed <= MAX_SAMPLE_SIZE:
        return parsed, None
    return None, {
        "success": False,
        "error_code": "invalid_sample_size",
        "error": (
            f"sample_size must be an integer from {MIN_SAMPLE_SIZE} through "
            f"{MAX_SAMPLE_SIZE}; received {candidate!r}."
        ),
        "message": "Choose a bounded file sample size and retry.",
    }


def normalize_binary_threshold(value):
    try:
        parsed = None if isinstance(value, bool) else float(value)
    except (TypeError, ValueError, OverflowError):
        parsed = None
    if parsed is not None and math.isfinite(parsed) and 0 < parsed <= 100:
        return parsed, None
    return None, {
        "success": False,
        "error_code": "invalid_binary_threshold",
        "error": (
            "binary_threshold must be finite, greater than 0, and at most "
            f"100; received {value!r}."
        ),
        "message": "Choose a valid binary threshold and retry.",
    }


def normalize_boolean(value, *, field, command_base):
    if isinstance(value, bool):
        return value, None
    parsed = command_base._parse_bool(value)
    if parsed is not None:
        return parsed, None
    return None, {
        "success": False,
        "error_code": f"invalid_{field}",
        "error": f"{field} must be true or false; received {value!r}.",
        "message": f"Choose a valid {field} value and retry.",
    }


def _distributed_segment_specs(file_size, budget):
    if file_size == 0:
        return []
    if file_size <= budget:
        return [(0, file_size)]
    first_size = (budget + 2) // 3
    middle_size = (budget + 1) // 3
    end_size = budget - first_size - middle_size
    middle_offset = max(first_size, (file_size - middle_size) // 2)
    return [
        (0, first_size),
        (middle_offset, middle_size),
        (file_size - end_size, end_size),
    ]


def read_distributed_sample(target, sample_size, *, open_file=open):
    """Read one stable start/middle/end sample under a global byte budget."""
    initial = regular_file_fingerprint(target.analyzed_path)
    if initial != target.fingerprint:
        raise FileChangedDuringReadError(
            "The file changed between path validation and sample reading."
        )
    segments = _read_segments(target, sample_size, open_file)
    if regular_file_fingerprint(target.analyzed_path) != initial:
        raise FileChangedDuringReadError(
            "The file changed while its distributed sample was being read."
        )
    return FileSample(target.file_size, sample_size, tuple(segments))


def _read_segments(target, sample_size, open_file):
    segments = []
    with open_file(target.analyzed_path, "rb") as file_handle:
        for offset, requested in _distributed_segment_specs(target.file_size, sample_size):
            file_handle.seek(offset)
            data = file_handle.read(requested)
            if len(data) != requested:
                raise FileChangedDuringReadError(
                    "A distributed sample segment ended before its validated byte range was available."
                )
            segments.append(SampleSegment(offset, requested, data))
    return segments
