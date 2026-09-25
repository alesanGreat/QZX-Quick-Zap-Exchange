"""Strict, resumable decoding for readFile; never silently replace file bytes."""

from __future__ import annotations

import codecs
from dataclasses import dataclass
import re

DEFAULT_READ_BYTES = 64 * 1024
MAX_READ_BYTES = 16 * 1024 * 1024
_BOMS = (
    (codecs.BOM_UTF32_LE, "utf-32-le"),
    (codecs.BOM_UTF32_BE, "utf-32-be"),
    (codecs.BOM_UTF8, "utf-8"),
    (codecs.BOM_UTF16_LE, "utf-16-le"),
    (codecs.BOM_UTF16_BE, "utf-16-be"),
)
_ENCODINGS = {
    "utf-8", "utf-8-sig", "utf-16", "utf-16-le", "utf-16-be",
    "utf-32", "utf-32-le", "utf-32-be", "ascii", "iso8859-1", "cp1252",
    "cp437", "cp850",
}


class ReadFileError(ValueError):
    """An actionable readFile error, without copying file contents into errors."""

    def __init__(self, code: str, message: str, **details):
        super().__init__(message)
        self.code = code
        self.details = details


@dataclass(frozen=True)
class ReadOptions:
    max_lines: int | None
    max_bytes: int
    offset: int
    encoding: str
    expected_fingerprint: str | None = None


def _integer(value, name: str, minimum: int, maximum: int | None = None) -> int:
    if isinstance(value, str) and re.fullmatch(r"[+]?[0-9]+", value.strip()):
        try:
            value = int(value)
        except ValueError as exc:
            raise ReadFileError(f"invalid_{name}", f"{name} is too large to parse.") from exc
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ReadFileError(f"invalid_{name}", f"{name} must be an integer >= {minimum}.")
    if maximum is not None and value > maximum:
        raise ReadFileError(f"invalid_{name}", f"{name} must not exceed {maximum}.")
    return value


def normalize_options(max_lines, max_bytes, offset, encoding, expected_fingerprint=None) -> ReadOptions:
    lines = None if max_lines is None else _integer(max_lines, "max_lines", 0)
    budget = _integer(max_bytes, "max_bytes", 1, MAX_READ_BYTES)
    position = _integer(offset, "offset", 0)
    if not isinstance(encoding, str) or not encoding.strip():
        raise ReadFileError("invalid_encoding", "Provide auto or a supported text encoding.")
    name = encoding.strip().lower()
    if name != "auto":
        try:
            name = codecs.lookup(name).name
        except LookupError as exc:
            raise ReadFileError("invalid_encoding", "Unknown text encoding.") from exc
        if name not in _ENCODINGS:
            raise ReadFileError(
                "unsupported_encoding",
                "Use UTF-8, UTF-16/32, ASCII, Latin-1, CP1252, CP437 or CP850. "
                "Stateful and binary codecs cannot be resumed by byte offset.",
            )
    if expected_fingerprint is not None and (
        not isinstance(expected_fingerprint, str)
        or re.fullmatch(r"[0-9a-f]{64}", expected_fingerprint) is None
    ):
        raise ReadFileError("invalid_expected_fingerprint", "Use the exact expected_fingerprint from next_read.")
    return ReadOptions(lines, budget, position, name, expected_fingerprint)


def resolve_encoding(probe: bytes, requested: str) -> tuple[str, int]:
    detected = next(((codec, len(bom)) for bom, codec in _BOMS if probe.startswith(bom)), None)
    if requested == "auto":
        return detected or ("utf-8", 0)
    codec = "utf-8" if requested == "utf-8-sig" else requested
    if detected is not None:
        matches = codec == detected[0] or (
            codec in {"utf-16", "utf-32"} and detected[0].startswith(codec + "-")
        )
        if not matches:
            raise ReadFileError("encoding_mismatch", "The requested encoding disagrees with the file BOM.")
        return detected
    if codec in {"utf-16", "utf-32"}:
        raise ReadFileError("encoding_bom_required", "Choose an explicit -le or -be encoding for a file without a BOM.")
    return codec, 0


def _code_unit(codec: str) -> int:
    return 4 if codec.startswith("utf-32") else 2 if codec.startswith("utf-16") else 1


def validate_offset(offset: int, size: int, codec: str, bom_size: int) -> None:
    if offset > size or (offset != 0 and offset < bom_size):
        raise ReadFileError("invalid_offset", "offset is outside the file or inside its BOM.")
    if offset and (offset - bom_size) % _code_unit(codec):
        raise ReadFileError("invalid_offset", "offset must align with an encoded character. Use next_read.")


def _line_end(data: bytes, codec: str, limit: int | None) -> tuple[int, bool]:
    if limit is None:
        return len(data), False
    if limit == 0:
        return 0, True
    cr, lf = "\r".encode(codec), "\n".encode(codec)
    pattern = re.compile(b"|".join(re.escape(item) for item in (cr + lf, cr, lf)))
    count = 0
    for match in pattern.finditer(data):
        if match.start() % _code_unit(codec):
            continue
        count += 1
        if count == limit:
            return match.end(), True
    return len(data), False


def decode_page(data: bytes, codec: str, *, eof: bool, max_lines: int | None):
    """Return exact text and consumed source bytes, leaving split characters unread."""
    unit = _code_unit(codec)
    safe = data if eof else data[:len(data) - len(data) % unit]
    cr = "\r".encode(codec)
    if not eof and safe.endswith(cr):
        safe = safe[:-len(cr)]  # Keep a possible CRLF together across pages.
    end, line_limit = _line_end(safe, codec, max_lines)
    selected = safe[:end]
    final = eof and end == len(data)
    decoder = codecs.getincrementaldecoder(codec)(errors="strict")
    try:
        content = decoder.decode(selected, final=final)
    except UnicodeDecodeError as exc:
        raise ReadFileError(
            "decode_failed",
            "File bytes are not valid for this encoding. Use --encoding with the known encoding; no text was replaced.",
            encoding=codec, relative_byte_offset=exc.start,
        ) from exc
    if "\x00" in content:
        raise ReadFileError("binary_content", "The decoded page contains NUL characters. Inspect its type with detectFileType.")
    consumed = len(selected) - len(decoder.getstate()[0])
    complete = eof and consumed == len(data)
    reason = None if complete else "max_lines" if line_limit else "max_bytes"
    return content, consumed, reason


def count_text_lines(content: str) -> int:
    count = len(re.findall(r"\r\n|\r|\n", content))
    return count + int(bool(content) and not content.endswith(("\r", "\n")))
