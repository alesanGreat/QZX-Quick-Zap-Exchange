"""Bounded, portable file-content analysis shared by QZX commands."""

from __future__ import annotations

from dataclasses import dataclass
import codecs
import math
import os
from pathlib import Path
import stat
import unicodedata

try:
    import chardet
except ImportError:  # A source checkout without dependencies remains importable.
    chardet = None


MIN_SAMPLE_SIZE = 64
MAX_SAMPLE_SIZE = 16 * 1024 * 1024
DEFAULT_BINARY_SAMPLE_SIZE = 8192
DEFAULT_TYPE_SAMPLE_SIZE = 64 * 1024

_MIME_EXTENSIONS = {
    "application/gzip": ("gz",),
    "application/json": ("json",),
    "application/msword": ("doc",),
    "application/octet-stream": ("bin", "dat"),
    "application/pdf": ("pdf",),
    "application/rtf": ("rtf",),
    "application/vnd.ms-excel": ("xls",),
    "application/vnd.ms-powerpoint": ("ppt",),
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": (
        "pptx",
    ),
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": (
        "xlsx",
    ),
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": (
        "docx",
    ),
    "application/vnd.sqlite3": ("sqlite", "sqlite3", "db"),
    "application/x-7z-compressed": ("7z",),
    "application/x-elf": ("elf",),
    "application/x-msdownload": ("exe", "dll"),
    "application/x-rar-compressed": ("rar",),
    "application/x-tar": ("tar",),
    "application/xml": ("xml",),
    "application/zip": ("zip",),
    "audio/flac": ("flac",),
    "audio/mpeg": ("mp3",),
    "audio/ogg": ("ogg", "oga"),
    "audio/wav": ("wav",),
    "font/otf": ("otf",),
    "font/ttf": ("ttf",),
    "font/woff": ("woff",),
    "font/woff2": ("woff2",),
    "image/bmp": ("bmp",),
    "image/gif": ("gif",),
    "image/jpeg": ("jpg", "jpeg"),
    "image/png": ("png",),
    "image/svg+xml": ("svg",),
    "image/tiff": ("tif", "tiff"),
    "image/webp": ("webp",),
    "text/css": ("css",),
    "text/csv": ("csv",),
    "text/html": ("html", "htm"),
    "text/javascript": ("js", "mjs", "cjs"),
    "text/markdown": ("md", "markdown"),
    "text/plain": ("txt", "text", "log", "ini", "conf"),
    "text/x-c": ("c", "h"),
    "text/x-c++": ("cpp", "cxx", "cc", "hpp"),
    "text/x-csharp": ("cs",),
    "text/x-java": ("java",),
    "text/x-perl": ("pl",),
    "text/x-php": ("php",),
    "text/x-python": ("py", "pyw"),
    "text/x-ruby": ("rb",),
    "text/x-shellscript": ("sh", "bash", "zsh"),
    "text/x-sql": ("sql",),
    "text/x-yaml": ("yaml", "yml"),
    "video/mp4": ("mp4",),
    "video/quicktime": ("mov",),
    "video/webm": ("webm",),
    "video/x-matroska": ("mkv",),
    "video/x-msvideo": ("avi",),
}
_EXTENSION_MIME = {
    extension: mime_type
    for mime_type, extensions in _MIME_EXTENSIONS.items()
    for extension in extensions
}
_TEXTUAL_APPLICATION_MIMES = {
    "application/javascript",
    "application/json",
    "application/rtf",
    "application/xml",
    "application/x-httpd-php",
    "application/x-javascript",
    "application/x-yaml",
}
_MIME_DESCRIPTIONS = {
    "application/gzip": "gzip-compressed data",
    "application/json": "JSON text",
    "application/octet-stream": "unidentified binary data",
    "application/pdf": "PDF document",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": (
        "Office Open XML presentation"
    ),
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": (
        "Office Open XML spreadsheet"
    ),
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": (
        "Office Open XML document"
    ),
    "application/vnd.sqlite3": "SQLite database",
    "application/x-7z-compressed": "7-Zip archive",
    "application/x-elf": "ELF executable or object",
    "application/x-msdownload": "Windows portable executable",
    "application/x-rar-compressed": "RAR archive",
    "application/zip": "ZIP archive",
    "audio/flac": "FLAC audio",
    "audio/mpeg": "MPEG audio",
    "audio/ogg": "Ogg audio",
    "audio/wav": "WAVE audio",
    "image/bmp": "BMP image",
    "image/gif": "GIF image",
    "image/jpeg": "JPEG image",
    "image/png": "PNG image",
    "image/tiff": "TIFF image",
    "image/webp": "WebP image",
    "text/html": "HTML text",
    "text/plain": "plain text",
    "video/mp4": "MP4 video",
    "video/webm": "WebM video",
    "video/x-msvideo": "AVI video",
}


class FileChangedDuringReadError(OSError):
    """Raised when a validated regular file changes during bounded reading."""


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
            "fingerprint": {
                "size_bytes": self.fingerprint[0],
                "modified_ns": self.fingerprint[1],
                "device": self.fingerprint[2],
                "inode": self.fingerprint[3],
            },
        }


class DirectoryChangedDuringScanError(OSError):
    """Raised when a validated directory changes during enumeration."""


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
            "fingerprint": {
                "size_bytes": self.fingerprint[0],
                "modified_ns": self.fingerprint[1],
                "device": self.fingerprint[2],
                "inode": self.fingerprint[3],
            },
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


@dataclass(frozen=True)
class DetectedType:
    mime_type: str
    description: str
    source: str
    confidence: float

    def evidence(self):
        return {
            "mime_type": self.mime_type,
            "description": self.description,
            "source": self.source,
            "confidence": round(self.confidence, 2),
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
    if stat.S_ISREG(mode):
        return "regular_file"
    if stat.S_ISDIR(mode):
        return "directory"
    if stat.S_ISFIFO(mode):
        return "fifo"
    if stat.S_ISSOCK(mode):
        return "socket"
    if stat.S_ISCHR(mode):
        return "character_device"
    if stat.S_ISBLK(mode):
        return "block_device"
    return "special_entry"


def validate_regular_file(file_path, *, follow_symlinks=False):
    """Resolve one bounded regular-file target or return a QZX failure."""
    try:
        raw_path = os.fspath(file_path)
    except TypeError:
        return None, _path_failure(
            "invalid_file_path",
            "file_path must be text or a path-like object.",
            "Provide a valid file path to analyze.",
            requested_path=repr(file_path),
        )
    if not isinstance(raw_path, str):
        return None, _path_failure(
            "invalid_file_path",
            "file_path must resolve to text, not raw bytes.",
            "Provide a text file path to analyze.",
            requested_path=repr(file_path),
        )
    if not raw_path:
        return None, _path_failure(
            "invalid_file_path",
            "file_path must not be empty.",
            "Provide a non-empty file path to analyze.",
            requested_path=raw_path,
        )
    if "\x00" in raw_path:
        return None, _path_failure(
            "invalid_file_path",
            "file_path must not contain NUL bytes.",
            "Provide a valid file path to analyze.",
            requested_path=raw_path,
        )

    try:
        absolute_path = Path(os.path.abspath(os.path.expanduser(raw_path)))
        if not os.path.lexists(absolute_path):
            return None, _path_failure(
                "file_not_found",
                f"File '{absolute_path}' does not exist.",
                "The requested file was not found.",
                requested_path=raw_path,
                file_path=str(absolute_path),
            )
        link_components = tuple(
            str(component)
            for component in _path_components(absolute_path)
            if _is_link_or_junction(component)
        )
        if link_components and not follow_symlinks:
            return None, _path_failure(
                "symlink_path_blocked",
                "File analysis does not follow symbolic links or junctions by "
                "default.",
                "Review the resolved target, then set follow_symlinks=true if "
                "that target is intentional.",
                requested_path=raw_path,
                file_path=str(absolute_path),
                blocked_component=link_components[0],
                link_components=list(link_components),
            )
        analyzed_path = (
            absolute_path.resolve(strict=True)
            if link_components
            else absolute_path
        )
        file_stat = os.stat(analyzed_path, follow_symlinks=True)
    except (OSError, RuntimeError, ValueError) as exc:
        return None, _path_failure(
            "file_inspection_failed",
            f"{type(exc).__name__}: {exc}",
            "QZX could not inspect the requested file path.",
            requested_path=raw_path,
        )

    entry_type = _entry_type(file_stat.st_mode)
    if entry_type != "regular_file":
        return None, _path_failure(
            "not_a_regular_file",
            f"'{analyzed_path}' is {entry_type}, not a regular file.",
            "File-content analysis accepts only regular files.",
            requested_path=raw_path,
            file_path=str(absolute_path),
            analyzed_path=str(analyzed_path),
            entry_type=entry_type,
        )

    fingerprint = _stat_fingerprint(file_stat)
    return (
        FileTarget(
            requested_path=raw_path,
            absolute_path=absolute_path,
            analyzed_path=analyzed_path,
            file_size=file_stat.st_size,
            followed_link=bool(link_components),
            link_components=link_components,
            fingerprint=fingerprint,
        ),
        None,
    )


def validate_directory(directory_path, *, follow_symlinks=False):
    """Resolve one real directory target or return a structured QZX failure."""
    try:
        raw_path = os.fspath(directory_path)
    except TypeError:
        return None, _path_failure(
            "invalid_directory_path",
            "directory_path must be text or a path-like object.",
            "Provide a valid directory path to inspect.",
            requested_path=repr(directory_path),
        )
    if not isinstance(raw_path, str):
        return None, _path_failure(
            "invalid_directory_path",
            "directory_path must resolve to text, not raw bytes.",
            "Provide a text directory path to inspect.",
            requested_path=repr(directory_path),
        )
    if not raw_path:
        return None, _path_failure(
            "invalid_directory_path",
            "directory_path must not be empty.",
            "Provide a non-empty directory path to inspect.",
            requested_path=raw_path,
        )
    if "\x00" in raw_path:
        return None, _path_failure(
            "invalid_directory_path",
            "directory_path must not contain NUL bytes.",
            "Provide a valid directory path to inspect.",
            requested_path=raw_path,
        )

    try:
        absolute_path = Path(os.path.abspath(os.path.expanduser(raw_path)))
        if not os.path.lexists(absolute_path):
            return None, _path_failure(
                "directory_not_found",
                f"Directory '{absolute_path}' does not exist.",
                "The requested directory was not found.",
                requested_path=raw_path,
                directory_path=str(absolute_path),
            )
        link_components = tuple(
            str(component)
            for component in _path_components(absolute_path)
            if _is_link_or_junction(component)
        )
        if link_components and not follow_symlinks:
            return None, _path_failure(
                "symlink_path_blocked",
                "Directory inspection does not follow symbolic links or "
                "junctions by default.",
                "Review the resolved target, then set follow_symlinks=true if "
                "that target is intentional.",
                requested_path=raw_path,
                directory_path=str(absolute_path),
                blocked_component=link_components[0],
                link_components=list(link_components),
            )
        analyzed_path = (
            absolute_path.resolve(strict=True)
            if link_components
            else absolute_path
        )
        target_stat = os.stat(analyzed_path, follow_symlinks=True)
    except (OSError, RuntimeError, ValueError) as exc:
        return None, _path_failure(
            "directory_inspection_failed",
            f"{type(exc).__name__}: {exc}",
            "QZX could not inspect the requested directory path.",
            requested_path=raw_path,
        )

    if not stat.S_ISDIR(target_stat.st_mode):
        return None, _path_failure(
            "not_a_directory",
            f"'{analyzed_path}' is not a directory.",
            "Directory inspection requires a directory target.",
            requested_path=raw_path,
            directory_path=str(absolute_path),
            analyzed_path=str(analyzed_path),
        )

    return (
        DirectoryTarget(
            requested_path=raw_path,
            absolute_path=absolute_path,
            analyzed_path=analyzed_path,
            followed_link=bool(link_components),
            link_components=link_components,
            fingerprint=_stat_fingerprint(target_stat),
        ),
        None,
    )


def directory_fingerprint(path):
    directory_stat = os.stat(path, follow_symlinks=True)
    if not stat.S_ISDIR(directory_stat.st_mode):
        raise DirectoryChangedDuringScanError(
            f"Validated target '{path}' is no longer a directory."
        )
    return _stat_fingerprint(directory_stat)


def _stat_fingerprint(file_stat):
    return (
        file_stat.st_size,
        getattr(file_stat, "st_mtime_ns", None),
        file_stat.st_dev,
        file_stat.st_ino,
    )


def regular_file_fingerprint(path):
    file_stat = os.stat(path, follow_symlinks=True)
    if not stat.S_ISREG(file_stat.st_mode):
        raise FileChangedDuringReadError(
            f"Validated target '{path}' is no longer a regular file."
        )
    return _stat_fingerprint(file_stat)


def _path_failure(error_code, error, message, **details):
    return {
        "success": False,
        "error_code": error_code,
        "error": error,
        "message": message,
        "details": details,
    }


def normalize_sample_size(value, *, default):
    if value is None:
        value = default
    if isinstance(value, bool):
        parsed = None
    else:
        try:
            parsed = int(value)
        except (TypeError, ValueError, OverflowError):
            parsed = None
    if parsed is None or not MIN_SAMPLE_SIZE <= parsed <= MAX_SAMPLE_SIZE:
        return None, {
            "success": False,
            "error_code": "invalid_sample_size",
            "error": (
                f"sample_size must be an integer from {MIN_SAMPLE_SIZE} through "
                f"{MAX_SAMPLE_SIZE}; received {value!r}."
            ),
            "message": "Choose a bounded file sample size and retry.",
        }
    return parsed, None


def normalize_binary_threshold(value):
    if isinstance(value, bool):
        parsed = None
    else:
        try:
            parsed = float(value)
        except (TypeError, ValueError, OverflowError):
            parsed = None
    if parsed is None or not math.isfinite(parsed) or not 0 < parsed <= 100:
        return None, {
            "success": False,
            "error_code": "invalid_binary_threshold",
            "error": (
                "binary_threshold must be finite, greater than 0, and at most "
                f"100; received {value!r}."
            ),
            "message": "Choose a valid binary threshold and retry.",
        }
    return parsed, None


def normalize_boolean(value, *, field, command_base):
    if isinstance(value, bool):
        return value, None
    parsed = command_base._parse_bool(value)
    if parsed is None:
        return None, {
            "success": False,
            "error_code": f"invalid_{field}",
            "error": f"{field} must be true or false; received {value!r}.",
            "message": f"Choose a valid {field} value and retry.",
        }
    return parsed, None


def _distributed_segment_specs(file_size, budget):
    if file_size == 0:
        return []
    if file_size <= budget:
        return [(0, file_size)]

    first_size = (budget + 2) // 3
    middle_size = (budget + 1) // 3
    end_size = budget - first_size - middle_size
    middle_offset = max(first_size, (file_size - middle_size) // 2)
    end_offset = file_size - end_size
    return [
        (0, first_size),
        (middle_offset, middle_size),
        (end_offset, end_size),
    ]


def read_distributed_sample(target, sample_size, *, open_file=open):
    """Read one stable start/middle/end sample under a global byte budget."""
    initial_fingerprint = regular_file_fingerprint(target.analyzed_path)
    if initial_fingerprint != target.fingerprint:
        raise FileChangedDuringReadError(
            "The file changed between path validation and sample reading."
        )

    segments = []
    with open_file(target.analyzed_path, "rb") as file_handle:
        for offset, requested_bytes in _distributed_segment_specs(
            target.file_size,
            sample_size,
        ):
            file_handle.seek(offset)
            data = file_handle.read(requested_bytes)
            if len(data) != requested_bytes:
                raise FileChangedDuringReadError(
                    "A distributed sample segment ended before its validated "
                    "byte range was available."
                )
            segments.append(
                SampleSegment(
                    offset=offset,
                    requested_bytes=requested_bytes,
                    data=data,
                )
            )

    final_fingerprint = regular_file_fingerprint(target.analyzed_path)
    if final_fingerprint != initial_fingerprint:
        raise FileChangedDuringReadError(
            "The file changed while its distributed sample was being read."
        )
    return FileSample(
        file_size=target.file_size,
        budget_bytes=sample_size,
        segments=tuple(segments),
    )


def _signature_type(path, head):
    suffix = path.suffix.casefold().lstrip(".")
    if head.startswith(b"\xff\xd8\xff"):
        return DetectedType("image/jpeg", "JPEG image", "content_signature", 100)
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return DetectedType("image/png", "PNG image", "content_signature", 100)
    if head.startswith((b"GIF87a", b"GIF89a")):
        return DetectedType("image/gif", "GIF image", "content_signature", 100)
    if head.startswith(b"%PDF-"):
        return DetectedType("application/pdf", "PDF document", "content_signature", 100)
    if head.startswith(b"7z\xbc\xaf'\x1c"):
        return DetectedType(
            "application/x-7z-compressed",
            "7-Zip archive",
            "content_signature",
            100,
        )
    if head.startswith(b"Rar!\x1a\x07"):
        return DetectedType(
            "application/x-rar-compressed",
            "RAR archive",
            "content_signature",
            100,
        )
    if head.startswith(b"\x1f\x8b"):
        return DetectedType(
            "application/gzip",
            "gzip-compressed data",
            "content_signature",
            100,
        )
    if head.startswith(b"MZ"):
        return DetectedType(
            "application/x-msdownload",
            "Windows portable executable",
            "content_signature",
            100,
        )
    if head.startswith(b"\x7fELF"):
        return DetectedType(
            "application/x-elf",
            "ELF executable or object",
            "content_signature",
            100,
        )
    if head.startswith(b"SQLite format 3\x00"):
        return DetectedType(
            "application/vnd.sqlite3",
            "SQLite database",
            "content_signature",
            100,
        )
    if head.startswith((b"II*\x00", b"MM\x00*")):
        return DetectedType("image/tiff", "TIFF image", "content_signature", 100)
    if head.startswith(b"BM"):
        return DetectedType("image/bmp", "BMP image", "content_signature", 95)
    if head.startswith(b"fLaC"):
        return DetectedType("audio/flac", "FLAC audio", "content_signature", 100)
    if head.startswith(b"OggS"):
        return DetectedType("audio/ogg", "Ogg container", "content_signature", 95)
    if head.startswith(b"RIFF") and len(head) >= 12:
        riff_type = head[8:12]
        if riff_type == b"WAVE":
            return DetectedType("audio/wav", "WAVE audio", "content_signature", 100)
        if riff_type == b"AVI ":
            return DetectedType(
                "video/x-msvideo",
                "AVI video",
                "content_signature",
                100,
            )
        if riff_type == b"WEBP":
            return DetectedType("image/webp", "WebP image", "content_signature", 100)
    if len(head) >= 12 and head[4:8] == b"ftyp":
        return DetectedType(
            "video/mp4",
            "ISO Base Media file",
            "content_signature",
            90,
        )
    if head.startswith(b"PK\x03\x04"):
        office_mimes = {
            "docx": (
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "Office Open XML document",
            ),
            "xlsx": (
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "Office Open XML spreadsheet",
            ),
            "pptx": (
                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                "Office Open XML presentation",
            ),
        }
        if suffix in office_mimes:
            mime_type, description = office_mimes[suffix]
            return DetectedType(
                mime_type,
                description + " (ZIP container; subtype not verified)",
                "zip_container_plus_extension_hint",
                55,
            )
        return DetectedType("application/zip", "ZIP archive", "content_signature", 100)
    return None


def _decoded_control_percentage(text):
    if not text:
        return 0.0
    allowed = {"\b", "\t", "\n", "\f", "\r"}
    controls = sum(
        character == "\ufffd"
        or (
            unicodedata.category(character) == "Cc"
            and character not in allowed
        )
        for character in text
    )
    return controls * 100 / len(text)


def _try_decode(data, encoding, *, allow_incomplete_tail=False):
    try:
        if allow_incomplete_tail:
            decoder = codecs.getincrementaldecoder(encoding)(errors="strict")
            return decoder.decode(data, final=False)
        return data.decode(encoding, errors="strict")
    except (LookupError, UnicodeDecodeError):
        return None


def _detect_encoding(head, *, detect_encoding=None):
    if not head:
        return None, 100.0, 0.0, "empty"

    bom_encodings = (
        (b"\xff\xfe\x00\x00", "utf-32-le"),
        (b"\x00\x00\xfe\xff", "utf-32-be"),
        (b"\xef\xbb\xbf", "utf-8-sig"),
        (b"\xff\xfe", "utf-16-le"),
        (b"\xfe\xff", "utf-16-be"),
    )
    for bom, encoding in bom_encodings:
        if head.startswith(bom):
            unit = 4 if "32" in encoding else 2 if "16" in encoding else 1
            decodable = head[: len(head) - (len(head) % unit)]
            decoded = _try_decode(
                decodable,
                encoding,
                allow_incomplete_tail=True,
            )
            if decoded is not None:
                return (
                    encoding,
                    100.0,
                    _decoded_control_percentage(decoded),
                    "unicode_bom",
                )

    decoded = _try_decode(
        head,
        "utf-8",
        allow_incomplete_tail=True,
    )
    if decoded is not None:
        return (
            "utf-8",
            100.0,
            _decoded_control_percentage(decoded),
            "strict_utf8",
        )

    if len(head) >= 8:
        even = head[0::2]
        odd = head[1::2]
        even_null_ratio = even.count(0) / len(even)
        odd_null_ratio = odd.count(0) / len(odd)
        candidate = None
        if odd_null_ratio >= 0.30 and even_null_ratio <= 0.10:
            candidate = "utf-16-le"
        elif even_null_ratio >= 0.30 and odd_null_ratio <= 0.10:
            candidate = "utf-16-be"
        if candidate is not None:
            decodable = head[: len(head) - (len(head) % 2)]
            decoded = _try_decode(
                decodable,
                candidate,
                allow_incomplete_tail=True,
            )
            if decoded is not None:
                return (
                    candidate,
                    90.0,
                    _decoded_control_percentage(decoded),
                    "utf16_null_pattern",
                )

    detector = detect_encoding
    if detector is None and chardet is not None:
        detector = chardet.detect
    if detector is not None:
        try:
            detection = detector(head) or {}
            encoding = detection.get("encoding")
            confidence = float(detection.get("confidence") or 0) * 100
            if encoding and confidence >= 70:
                decoded = _try_decode(
                    head,
                    encoding,
                    allow_incomplete_tail=True,
                )
                if decoded is not None:
                    return (
                        encoding,
                        confidence,
                        _decoded_control_percentage(decoded),
                        "encoding_detector",
                    )
        except (LookupError, TypeError, ValueError):
            pass
    return None, 0.0, None, "undetected"


def analyze_binary_content(sample, *, threshold, path, detect_encoding=None):
    """Classify sampled content with explicit, inspectable evidence."""
    head = sample.head
    analyzed_bytes = sample.analyzed_bytes
    signature = _signature_type(path, head)
    if signature is not None and not is_textual_mime(signature.mime_type):
        return {
            "is_binary": True,
            "binary_score": 100.0,
            "binary_threshold": threshold,
            "detection_method": "content_signature",
            "encoding_detected": None,
            "encoding_confidence": 0.0,
            "encoding_detection_method": "not_applicable",
            "decoded_control_percentage": None,
            "null_byte_count": sum(
                segment.data.count(0) for segment in sample.segments
            ),
            "suspicious_byte_count": 0,
            "sampled_byte_count": analyzed_bytes,
            "ambiguous": False,
            "signature": signature.evidence(),
        }

    if analyzed_bytes == 0:
        return {
            "is_binary": False,
            "binary_score": 0.0,
            "binary_threshold": threshold,
            "detection_method": "empty_file",
            "encoding_detected": None,
            "encoding_confidence": 100.0,
            "encoding_detection_method": "empty",
            "decoded_control_percentage": 0.0,
            "null_byte_count": 0,
            "suspicious_byte_count": 0,
            "sampled_byte_count": 0,
            "ambiguous": False,
            "signature": None,
        }

    encoding, encoding_confidence, decoded_controls, encoding_method = (
        _detect_encoding(head, detect_encoding=detect_encoding)
    )
    null_count = sum(segment.data.count(0) for segment in sample.segments)
    allowed_controls = {8, 9, 10, 12, 13}
    suspicious_count = sum(
        (byte < 32 and byte not in allowed_controls) or byte == 127
        for segment in sample.segments
        for byte in segment.data
    )
    raw_score = suspicious_count * 100 / analyzed_bytes
    unicode_encoding = bool(
        encoding
        and encoding.casefold().replace("_", "-").startswith(
            ("utf-16", "utf-32")
        )
    )

    if null_count and not unicode_encoding:
        binary_score = 100.0
        is_binary = True
        method = "null_bytes"
    else:
        effective_score = (
            decoded_controls
            if unicode_encoding and decoded_controls is not None
            else max(raw_score, decoded_controls or 0.0)
        )
        binary_score = float(effective_score)
        is_binary = binary_score >= threshold
        method = (
            "suspicious_control_bytes"
            if is_binary
            else "text_encoding"
            if encoding is not None
            else "character_distribution"
        )

    return {
        "is_binary": is_binary,
        "binary_score": round(binary_score, 2),
        "binary_threshold": threshold,
        "detection_method": method,
        "encoding_detected": encoding,
        "encoding_confidence": round(encoding_confidence, 2),
        "encoding_detection_method": encoding_method,
        "decoded_control_percentage": (
            round(decoded_controls, 2)
            if decoded_controls is not None
            else None
        ),
        "null_byte_count": null_count,
        "suspicious_byte_count": suspicious_count,
        "sampled_byte_count": analyzed_bytes,
        "ambiguous": (
            not is_binary
            and encoding is None
            and abs(binary_score - threshold) <= 2
        ),
        "signature": signature.evidence() if signature is not None else None,
    }


def _text_content_type(path, head, encoding):
    decoders = [encoding] if encoding else []
    decoders.extend(["utf-8", "latin-1"])
    decoded = ""
    for decoder in dict.fromkeys(decoders):
        if not decoder:
            continue
        try:
            decoded = head.decode(decoder, errors="strict")
            break
        except (LookupError, UnicodeDecodeError):
            continue
    stripped = decoded.lstrip("\ufeff \t\r\n").casefold()
    if stripped.startswith("<?xml"):
        return DetectedType("application/xml", "XML text", "text_content", 95)
    if stripped.startswith(("<!doctype html", "<html")):
        return DetectedType("text/html", "HTML text", "text_content", 95)
    if stripped.startswith(("{", "[")) and path.suffix.casefold() == ".json":
        return DetectedType(
            "application/json",
            "JSON text",
            "content_plus_extension",
            85,
        )
    if stripped.startswith("#!"):
        first_line = stripped.splitlines()[0]
        if "python" in first_line:
            return DetectedType(
                "text/x-python",
                "Python source text",
                "shebang",
                90,
            )
        if any(shell in first_line for shell in ("/sh", "bash", "zsh")):
            return DetectedType(
                "text/x-shellscript",
                "shell script text",
                "shebang",
                90,
            )
    suffix = path.suffix.casefold().lstrip(".")
    extension_mime = _EXTENSION_MIME.get(suffix)
    if extension_mime and is_textual_mime(extension_mime):
        return DetectedType(
            extension_mime,
            _MIME_DESCRIPTIONS.get(extension_mime, f"{extension_mime} text"),
            "text_classification_plus_extension",
            75,
        )
    return DetectedType("text/plain", "plain text", "text_classification", 70)


def detect_builtin_type(path, sample, binary_analysis):
    signature = _signature_type(path, sample.head)
    if signature is not None:
        return signature
    if not binary_analysis["is_binary"]:
        return _text_content_type(
            path,
            sample.head,
            binary_analysis.get("encoding_detected"),
        )

    suffix = path.suffix.casefold().lstrip(".")
    extension_mime = _EXTENSION_MIME.get(suffix)
    if extension_mime and not is_textual_mime(extension_mime):
        return DetectedType(
            extension_mime,
            _MIME_DESCRIPTIONS.get(
                extension_mime,
                f"binary data associated with {extension_mime}",
            ),
            "binary_classification_plus_extension",
            60,
        )
    return DetectedType(
        "application/octet-stream",
        "unidentified binary data",
        "binary_classification",
        50,
    )


def normalize_mime_type(value):
    if not isinstance(value, str):
        return None
    normalized = value.partition(";")[0].strip().casefold()
    if "/" not in normalized:
        return None
    return normalized


def common_extensions_for_mime(mime_type):
    return list(_MIME_EXTENSIONS.get(normalize_mime_type(mime_type), ()))


def is_textual_mime(mime_type):
    normalized = normalize_mime_type(mime_type)
    if normalized is None:
        return False
    return (
        normalized.startswith("text/")
        or normalized in _TEXTUAL_APPLICATION_MIMES
        or normalized.endswith(("+json", "+xml"))
        or normalized == "image/svg+xml"
    )


def categorize_mime_type(mime_type):
    normalized = normalize_mime_type(mime_type) or "application/octet-stream"
    categories = []
    major = normalized.partition("/")[0]
    major_categories = {
        "audio": "Audio",
        "font": "Font",
        "image": "Image",
        "text": "Text",
        "video": "Video",
    }
    if major in major_categories:
        categories.append(major_categories[major])
    if is_textual_mime(normalized) and "Text" not in categories:
        categories.append("Text")
    if normalized in {
        "application/gzip",
        "application/x-7z-compressed",
        "application/x-rar-compressed",
        "application/x-tar",
        "application/zip",
    }:
        categories.append("Archive")
    if normalized in {
        "application/msword",
        "application/pdf",
        "application/rtf",
        "application/vnd.ms-excel",
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }:
        categories.append("Document")
    if normalized in {
        "application/x-elf",
        "application/x-msdownload",
    }:
        categories.append("Executable")
    if normalized == "application/vnd.sqlite3":
        categories.append("Database")
    if normalized.startswith("text/x-") or normalized in {
        "application/javascript",
        "application/x-httpd-php",
        "text/javascript",
    }:
        categories.append("Source Code")
    if not categories:
        categories.append("Other")
    return categories
