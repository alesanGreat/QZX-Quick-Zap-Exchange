"""Bounded regular-file I/O and evidence for the readFile command."""

from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
import stat

from qzx.core.file_content_analysis import (
    FileChangedDuringReadError,
    regular_file_fingerprint,
    validate_regular_file,
)
from ._read_file_text import (
    ReadFileError, ReadOptions, count_text_lines, decode_page,
    resolve_encoding, validate_offset,
)


def _descriptor_fingerprint(stream):
    snapshot = os.fstat(stream.fileno())
    if not stat.S_ISREG(snapshot.st_mode):
        raise FileChangedDuringReadError("The opened target is no longer a regular file.")
    return (snapshot.st_size, snapshot.st_mtime_ns, snapshot.st_dev, snapshot.st_ino)


@contextmanager
def _open_verified(target, *, descriptor_fingerprint=_descriptor_fingerprint):
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(target.analyzed_path, flags)
    with os.fdopen(descriptor, "rb", buffering=0) as stream:
        if descriptor_fingerprint(stream) != target.fingerprint:
            raise FileChangedDuringReadError("The file changed before it could be read.")
        yield stream
        if descriptor_fingerprint(stream) != target.fingerprint:
            raise FileChangedDuringReadError("The file changed while it was being read.")
        if regular_file_fingerprint(target.absolute_path) != target.fingerprint:
            raise FileChangedDuringReadError("The requested path changed while it was being read.")


def _read_snapshot(stream, target, options: ReadOptions):
    probe = stream.read(4)
    codec, bom_size = resolve_encoding(probe, options.encoding)
    validate_offset(options.offset, target.file_size, codec, bom_size)
    wanted = 0 if options.max_lines == 0 else min(options.max_bytes, target.file_size - options.offset)
    stream.seek(options.offset)
    data = stream.read(wanted)
    if len(data) != wanted:
        raise FileChangedDuringReadError("The regular file produced an incomplete read.")
    skipped_bom = bom_size if options.offset == 0 and wanted else 0
    if skipped_bom > len(data):
        raise ReadFileError("read_limit_too_small", "Increase max_bytes to include the BOM and at least one character.")
    eof = options.offset + len(data) == target.file_size
    content, consumed, reason = decode_page(
        data[skipped_bom:], codec, eof=eof, max_lines=options.max_lines,
    )
    advance = consumed + skipped_bom
    if not advance and not eof and options.max_lines != 0:
        raise ReadFileError("read_limit_too_small", "Increase max_bytes to fit at least one complete character or newline.")
    return content, codec, advance, len(data) + len(probe), reason


def _continuation(path: str, options: ReadOptions, codec: str, next_offset, fingerprint):
    if next_offset is None or options.max_lines == 0:
        return None
    return {
        "file_path": path,
        "max_lines": options.max_lines,
        "max_bytes": options.max_bytes,
        "offset": next_offset,
        "encoding": codec,
        "expected_fingerprint": fingerprint,
    }


def _success_result(target, options, page, format_bytes):
    content, codec, advance, source_bytes_read, reason = page
    position = options.offset + advance
    complete = position == target.file_size
    lines = count_text_lines(content)
    next_offset = None if complete else position
    path = str(target.absolute_path)
    fingerprint = _fingerprint_token(target)
    details = {
        "path": path,
        "size": target.file_size,
        "size_readable": format_bytes(target.file_size),
        "modified": target.fingerprint[1] / 1_000_000_000,
        "encoding": codec,
        "offset": options.offset,
        "max_bytes": options.max_bytes,
        "bytes_consumed": advance,
        "source_bytes_read": source_bytes_read,
        "lines_read": lines,
        "total_lines": lines if complete and options.offset == 0 else "unknown",
        "read_complete": complete,
        "entire_file_read": complete and options.offset == 0,
        "truncated_by": None if complete else reason,
        "ends_with_partial_line": not complete and bool(content) and not content.endswith(("\r", "\n")),
        "next_offset": next_offset,
        "next_read": _continuation(path, options, codec, next_offset, fingerprint),
        "fingerprint_token": fingerprint,
        "fingerprint": target.evidence()["fingerprint"],
        "followed_symlink": target.followed_link,
    }
    message = f"Read {lines} line(s), {advance} source byte(s) from '{path}' ({codec})."
    if not complete:
        details["note"] = _partial_note(options, reason, position)
        message += " " + details["note"]
    return {"success": True, "message": message, "content": content, "details": details}


def _partial_note(options, reason, position):
    if options.max_lines == 0:
        return "No content requested. Increase max_lines to read text; this is not an end-of-file result."
    return f"Partial read: {reason}. Next byte offset: {position}; use the complete next_read values in --json output."


def _fingerprint_token(target):
    # This hashes metadata, not file contents. It detects ordinary changes, not
    # hostile edits that restore size and timestamps; it is not a content proof.
    identity = [str(target.absolute_path), *target.fingerprint]
    return hashlib.sha256(json.dumps(identity, ensure_ascii=True).encode("ascii")).hexdigest()


def read_file_page(
    file_path,
    options: ReadOptions,
    format_bytes,
    *,
    validator=validate_regular_file,
    opener=_open_verified,
):
    """Preserve ordinary symlink reads with explicit validation/open boundaries."""
    target, error = validator(file_path, follow_symlinks=True)
    if error is not None:
        return error
    if options.expected_fingerprint is not None and options.expected_fingerprint != _fingerprint_token(target):
        raise ReadFileError(
            "file_changed_since_previous_read",
            "The file metadata differs from the previous page. Restart at offset 0 without expected_fingerprint; do not combine these pages.",
        )
    with opener(target) as stream:
        page = _read_snapshot(stream, target, options)
    return _success_result(target, options, page, format_bytes)


def read_error_result(error: Exception, file_path):
    if isinstance(error, ReadFileError):
        code, message, details = error.code, str(error), error.details
    elif isinstance(error, FileChangedDuringReadError):
        code, message, details = "file_changed_during_read", str(error), {}
    elif isinstance(error, PermissionError):
        code, message, details = "permission_denied", "Check that you can read the requested file.", {}
    else:
        code, message, details = "read_failed", "Could not read the requested file.", {}
    return {
        "success": False, "error_code": code, "error": str(error),
        "message": message, "details": {"requested_path": str(file_path), **details},
    }
