"""Bounded, portable file-content analysis shared by QZX commands."""

from __future__ import annotations

import codecs
import unicodedata

try:
    import chardet
except ImportError:  # A source checkout without dependencies remains importable.
    chardet = None

from qzx.core.file_signatures import DetectedType, signature_type
from qzx.core.file_targets import (
    DEFAULT_BINARY_SAMPLE_SIZE,
    DEFAULT_TYPE_SAMPLE_SIZE,
    MAX_SAMPLE_SIZE,
    MIN_SAMPLE_SIZE,
    DirectoryChangedDuringScanError,
    DirectoryTarget,
    FileChangedDuringReadError,
    FileSample,
    FileTarget,
    SampleSegment,
    directory_fingerprint,
    normalize_binary_threshold,
    normalize_boolean,
    normalize_sample_size,
    read_distributed_sample,
    regular_file_fingerprint,
    validate_directory,
    validate_regular_file,
)
from qzx.core.file_type_data import (
    EXTENSION_MIME,
    MIME_DESCRIPTIONS,
    MIME_EXTENSIONS,
    TEXTUAL_APPLICATION_MIMES,
)

__all__ = [
    "DEFAULT_BINARY_SAMPLE_SIZE",
    "DEFAULT_TYPE_SAMPLE_SIZE",
    "MAX_SAMPLE_SIZE",
    "MIN_SAMPLE_SIZE",
    "DetectedType",
    "DirectoryChangedDuringScanError",
    "DirectoryTarget",
    "FileChangedDuringReadError",
    "FileSample",
    "FileTarget",
    "SampleSegment",
    "analyze_binary_content",
    "categorize_mime_type",
    "common_extensions_for_mime",
    "detect_builtin_type",
    "directory_fingerprint",
    "is_textual_mime",
    "normalize_binary_threshold",
    "normalize_boolean",
    "normalize_mime_type",
    "normalize_sample_size",
    "read_distributed_sample",
    "regular_file_fingerprint",
    "validate_directory",
    "validate_regular_file",
]


# Preserve the established module-level data and helper names for consumers.
_MIME_EXTENSIONS = MIME_EXTENSIONS
_EXTENSION_MIME = EXTENSION_MIME
_TEXTUAL_APPLICATION_MIMES = TEXTUAL_APPLICATION_MIMES
_MIME_DESCRIPTIONS = MIME_DESCRIPTIONS
_signature_type = signature_type


def _decoded_control_percentage(text):
    if not text:
        return 0.0
    allowed = {"\b", "\t", "\n", "\f", "\r"}
    controls = sum(
        character == "\ufffd"
        or unicodedata.category(character) == "Cc" and character not in allowed
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
    detected = _bom_encoding(head)
    if detected is not None:
        return detected
    decoded = _try_decode(head, "utf-8", allow_incomplete_tail=True)
    if decoded is not None:
        return "utf-8", 100.0, _decoded_control_percentage(decoded), "strict_utf8"
    detected = _utf16_pattern_encoding(head)
    if detected is not None:
        return detected
    detector = detect_encoding
    if detector is None and chardet is not None:
        detector = chardet.detect
    return _external_encoding(head, detector)


def _bom_encoding(head):
    encodings = (
        (b"\xff\xfe\x00\x00", "utf-32-le"),
        (b"\x00\x00\xfe\xff", "utf-32-be"),
        (b"\xef\xbb\xbf", "utf-8-sig"),
        (b"\xff\xfe", "utf-16-le"),
        (b"\xfe\xff", "utf-16-be"),
    )
    for bom, encoding in encodings:
        if not head.startswith(bom):
            continue
        unit = 4 if "32" in encoding else 2 if "16" in encoding else 1
        decodable = head[: len(head) - (len(head) % unit)]
        decoded = _try_decode(decodable, encoding, allow_incomplete_tail=True)
        if decoded is not None:
            return encoding, 100.0, _decoded_control_percentage(decoded), "unicode_bom"
    return None


def _utf16_pattern_encoding(head):
    if len(head) < 8:
        return None
    even, odd = head[0::2], head[1::2]
    even_null_ratio = even.count(0) / len(even)
    odd_null_ratio = odd.count(0) / len(odd)
    if odd_null_ratio >= 0.30 and even_null_ratio <= 0.10:
        candidate = "utf-16-le"
    elif even_null_ratio >= 0.30 and odd_null_ratio <= 0.10:
        candidate = "utf-16-be"
    else:
        return None
    decodable = head[: len(head) - (len(head) % 2)]
    decoded = _try_decode(decodable, candidate, allow_incomplete_tail=True)
    if decoded is None:
        return None
    return candidate, 90.0, _decoded_control_percentage(decoded), "utf16_null_pattern"


def _external_encoding(head, detector):
    if detector is None:
        return None, 0.0, None, "undetected"
    try:
        detection = detector(head) or {}
        encoding = detection.get("encoding")
        confidence = float(detection.get("confidence") or 0) * 100
        decoded = (
            _try_decode(head, encoding, allow_incomplete_tail=True)
            if encoding and confidence >= 70 else None
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
    signature = _signature_type(path, sample.head)
    if signature is not None and not is_textual_mime(signature.mime_type):
        return _signature_binary_result(sample, threshold, signature)
    if sample.analyzed_bytes == 0:
        return _empty_binary_result(threshold)
    facts = _sample_character_facts(sample, detect_encoding)
    binary_score, is_binary, method = _classify_character_facts(facts, threshold)
    return _binary_result(sample, threshold, signature, facts, binary_score, is_binary, method)


def _signature_binary_result(sample, threshold, signature):
    return {
        "is_binary": True,
        "binary_score": 100.0,
        "binary_threshold": threshold,
        "detection_method": "content_signature",
        "encoding_detected": None,
        "encoding_confidence": 0.0,
        "encoding_detection_method": "not_applicable",
        "decoded_control_percentage": None,
        "null_byte_count": sum(segment.data.count(0) for segment in sample.segments),
        "suspicious_byte_count": 0,
        "sampled_byte_count": sample.analyzed_bytes,
        "ambiguous": False,
        "signature": signature.evidence(),
    }


def _empty_binary_result(threshold):
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


def _sample_character_facts(sample, detect_encoding):
    encoding, confidence, controls, method = _detect_encoding(
        sample.head, detect_encoding=detect_encoding
    )
    null_count = sum(segment.data.count(0) for segment in sample.segments)
    allowed_controls = {8, 9, 10, 12, 13}
    suspicious_count = sum(
        (byte < 32 and byte not in allowed_controls) or byte == 127
        for segment in sample.segments for byte in segment.data
    )
    return {
        "encoding": encoding,
        "confidence": confidence,
        "controls": controls,
        "encoding_method": method,
        "null_count": null_count,
        "suspicious_count": suspicious_count,
        "raw_score": suspicious_count * 100 / sample.analyzed_bytes,
        "unicode_encoding": bool(
            encoding and encoding.casefold().replace("_", "-").startswith(("utf-16", "utf-32"))
        ),
    }


def _classify_character_facts(facts, threshold):
    if facts["null_count"] and not facts["unicode_encoding"]:
        return 100.0, True, "null_bytes"
    score = (
        facts["controls"]
        if facts["unicode_encoding"] and facts["controls"] is not None
        else max(facts["raw_score"], facts["controls"] or 0.0)
    )
    is_binary = float(score) >= threshold
    if is_binary:
        method = "suspicious_control_bytes"
    elif facts["encoding"] is not None:
        method = "text_encoding"
    else:
        method = "character_distribution"
    return float(score), is_binary, method


def _binary_result(sample, threshold, signature, facts, score, is_binary, method):
    controls = facts["controls"]
    return {
        "is_binary": is_binary,
        "binary_score": round(score, 2),
        "binary_threshold": threshold,
        "detection_method": method,
        "encoding_detected": facts["encoding"],
        "encoding_confidence": round(facts["confidence"], 2),
        "encoding_detection_method": facts["encoding_method"],
        "decoded_control_percentage": round(controls, 2) if controls is not None else None,
        "null_byte_count": facts["null_count"],
        "suspicious_byte_count": facts["suspicious_count"],
        "sampled_byte_count": sample.analyzed_bytes,
        "ambiguous": (
            not is_binary and facts["encoding"] is None and abs(score - threshold) <= 2
        ),
        "signature": signature.evidence() if signature is not None else None,
    }


def _text_content_type(path, head, encoding):
    decoded = _decode_text_probe(head, encoding)
    stripped = decoded.lstrip("\ufeff \t\r\n").casefold()
    markup = _markup_content_type(stripped, path)
    if markup is not None:
        return markup
    shebang = _shebang_content_type(stripped)
    if shebang is not None:
        return shebang
    extension_mime = _EXTENSION_MIME.get(path.suffix.casefold().lstrip("."))
    if extension_mime and is_textual_mime(extension_mime):
        return DetectedType(
            extension_mime,
            _MIME_DESCRIPTIONS.get(extension_mime, f"{extension_mime} text"),
            "text_classification_plus_extension",
            75,
        )
    return DetectedType("text/plain", "plain text", "text_classification", 70)


def _decode_text_probe(head, encoding):
    decoders = [encoding] if encoding else []
    decoders.extend(["utf-8", "latin-1"])
    for decoder in dict.fromkeys(decoders):
        if not decoder:
            continue
        try:
            return head.decode(decoder, errors="strict")
        except (LookupError, UnicodeDecodeError):
            continue
    return ""


def _markup_content_type(stripped, path):
    if stripped.startswith("<?xml"):
        return DetectedType("application/xml", "XML text", "text_content", 95)
    if stripped.startswith(("<!doctype html", "<html")):
        return DetectedType("text/html", "HTML text", "text_content", 95)
    if stripped.startswith(("{", "[")) and path.suffix.casefold() == ".json":
        return DetectedType("application/json", "JSON text", "content_plus_extension", 85)
    return None


def _shebang_content_type(stripped):
    if not stripped.startswith("#!"):
        return None
    first_line = stripped.splitlines()[0]
    if "python" in first_line:
        return DetectedType("text/x-python", "Python source text", "shebang", 90)
    if any(shell in first_line for shell in ("/sh", "bash", "zsh")):
        return DetectedType("text/x-shellscript", "shell script text", "shebang", 90)
    return None


def detect_builtin_type(path, sample, binary_analysis):
    signature = _signature_type(path, sample.head)
    if signature is not None:
        return signature
    if not binary_analysis["is_binary"]:
        return _text_content_type(path, sample.head, binary_analysis.get("encoding_detected"))
    extension_mime = _EXTENSION_MIME.get(path.suffix.casefold().lstrip("."))
    if extension_mime and not is_textual_mime(extension_mime):
        return DetectedType(
            extension_mime,
            _MIME_DESCRIPTIONS.get(
                extension_mime, f"binary data associated with {extension_mime}"
            ),
            "binary_classification_plus_extension",
            60,
        )
    return DetectedType(
        "application/octet-stream", "unidentified binary data", "binary_classification", 50
    )


def normalize_mime_type(value):
    if not isinstance(value, str):
        return None
    normalized = value.partition(";")[0].strip().casefold()
    return normalized if "/" in normalized else None


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
    major_categories = {
        "audio": "Audio", "font": "Font", "image": "Image",
        "text": "Text", "video": "Video",
    }
    major = normalized.partition("/")[0]
    if major in major_categories:
        categories.append(major_categories[major])
    if is_textual_mime(normalized) and "Text" not in categories:
        categories.append("Text")
    _append_application_categories(categories, normalized)
    if not categories:
        categories.append("Other")
    return categories


def _append_application_categories(categories, normalized):
    if normalized in {
        "application/gzip", "application/x-7z-compressed",
        "application/x-rar-compressed", "application/x-tar", "application/zip",
    }:
        categories.append("Archive")
    if normalized in {
        "application/msword", "application/pdf", "application/rtf",
        "application/vnd.ms-excel", "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }:
        categories.append("Document")
    if normalized in {"application/x-elf", "application/x-msdownload"}:
        categories.append("Executable")
    if normalized == "application/vnd.sqlite3":
        categories.append("Database")
    if normalized.startswith("text/x-") or normalized in {
        "application/javascript", "application/x-httpd-php", "text/javascript",
    }:
        categories.append("Source Code")
