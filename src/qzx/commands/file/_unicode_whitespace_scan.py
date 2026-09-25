"""Incremental Unicode whitespace scanning for isFileEmpty."""

from __future__ import annotations

import codecs


def scan_unicode_whitespace(command, target, encoding):
    """Prove whitespace-only text while detecting concurrent file changes."""
    decoder_factory, failure = _decoder_factory(encoding)
    if failure is not None:
        return failure

    bytes_scanned = 0
    try:
        initial_fingerprint = command._path_fingerprint(target.analyzed_path)
        if initial_fingerprint[0] != target.file_size:
            return command._changed_file_result(
                target,
                bytes_scanned,
                "The file size changed between path validation and opening.",
            )
        scan = _scan_stream(command, target, decoder_factory, encoding)
        if scan["terminal"] is not None:
            return scan["terminal"]
        bytes_scanned = scan["bytes_scanned"]
        final_fingerprint = command._path_fingerprint(target.analyzed_path)
    except OSError as exc:
        return _read_failure(encoding, bytes_scanned, exc)

    if bytes_scanned != target.file_size:
        return command._changed_file_result(
            target,
            bytes_scanned,
            "The number of bytes read no longer matches the validated size.",
        )
    if initial_fingerprint != final_fingerprint:
        return command._changed_file_result(
            target,
            bytes_scanned,
            "The file path changed while the whitespace scan was running.",
        )
    return {
        "success": True,
        "is_whitespace_only": True,
        "status": "whitespace_only",
        "bytes_scanned": bytes_scanned,
        "full_content_scanned": True,
    }


def _decoder_factory(encoding):
    try:
        return codecs.getincrementaldecoder(encoding), None
    except LookupError as exc:
        return None, {
            "success": False,
            "error_code": "text_decoder_unavailable",
            "error": f"{type(exc).__name__}: {exc}",
            "message": (
                f"QZX could not initialize the detected text decoder '{encoding}'."
            ),
            "details": {
                "text_encoding": encoding,
                "full_content_scanned": False,
                "whitespace_scan_bytes": 0,
            },
        }


def _scan_stream(command, target, decoder_factory, encoding):
    bytes_scanned = 0
    at_text_start = True
    try:
        with command._open_file(target.analyzed_path, "rb") as file_handle:
            decoder = decoder_factory(errors="strict")
            while True:
                chunk = file_handle.read(command._STREAM_CHUNK_SIZE)
                if not chunk:
                    break
                bytes_scanned += len(chunk)
                decoded, terminal = _decode(decoder, chunk, bytes_scanned, False)
                if terminal is not None:
                    return {"bytes_scanned": bytes_scanned, "terminal": terminal}
                character, at_text_start = command._first_non_whitespace(
                    decoded,
                    at_text_start=at_text_start,
                )
                if character is not None:
                    return {
                        "bytes_scanned": bytes_scanned,
                        "terminal": _non_whitespace(
                            character,
                            bytes_scanned,
                            False,
                        ),
                    }

            decoded, terminal = _decode(decoder, b"", bytes_scanned, True)
            if terminal is not None:
                return {"bytes_scanned": bytes_scanned, "terminal": terminal}
            character, _ = command._first_non_whitespace(
                decoded,
                at_text_start=at_text_start,
            )
            if character is not None:
                return {
                    "bytes_scanned": bytes_scanned,
                    "terminal": _non_whitespace(
                        character,
                        bytes_scanned,
                        True,
                    ),
                }
    except OSError as exc:
        return {
            "bytes_scanned": bytes_scanned,
            "terminal": _read_failure(encoding, bytes_scanned, exc),
        }
    return {"bytes_scanned": bytes_scanned, "terminal": None}


def _decode(decoder, chunk, bytes_scanned, final):
    try:
        return decoder.decode(chunk, final=final), None
    except UnicodeDecodeError as exc:
        return "", {
            "success": True,
            "is_whitespace_only": False,
            "status": "decode_error",
            "bytes_scanned": bytes_scanned,
            "full_content_scanned": final,
            "decode_error": f"{type(exc).__name__}: {exc}",
        }


def _non_whitespace(character, bytes_scanned, full_content_scanned):
    return {
        "success": True,
        "is_whitespace_only": False,
        "status": "non_whitespace_found",
        "bytes_scanned": bytes_scanned,
        "full_content_scanned": full_content_scanned,
        "first_non_whitespace_codepoint": f"U+{ord(character):04X}",
    }


def _read_failure(encoding, bytes_scanned, exc):
    return {
        "success": False,
        "error_code": "file_read_failed",
        "error": f"{type(exc).__name__}: {exc}",
        "message": "QZX could not complete the whitespace scan.",
        "details": {
            "phase": "whitespace_scan",
            "text_encoding": encoding,
            "full_content_scanned": False,
            "whitespace_scan_bytes": bytes_scanned,
        },
    }
