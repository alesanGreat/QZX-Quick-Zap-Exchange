"""Content-signature recognition for bounded QZX file samples."""

from __future__ import annotations

from dataclasses import dataclass


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


_FIXED_SIGNATURES = (
    ((b"\xff\xd8\xff",), "image/jpeg", "JPEG image", 100),
    ((b"\x89PNG\r\n\x1a\n",), "image/png", "PNG image", 100),
    ((b"GIF87a", b"GIF89a"), "image/gif", "GIF image", 100),
    ((b"%PDF-",), "application/pdf", "PDF document", 100),
    ((b"7z\xbc\xaf'\x1c",), "application/x-7z-compressed", "7-Zip archive", 100),
    ((b"Rar!\x1a\x07",), "application/x-rar-compressed", "RAR archive", 100),
    ((b"\x1f\x8b",), "application/gzip", "gzip-compressed data", 100),
    ((b"MZ",), "application/x-msdownload", "Windows portable executable", 100),
    ((b"\x7fELF",), "application/x-elf", "ELF executable or object", 100),
    ((b"SQLite format 3\x00",), "application/vnd.sqlite3", "SQLite database", 100),
    ((b"II*\x00", b"MM\x00*"), "image/tiff", "TIFF image", 100),
    ((b"BM",), "image/bmp", "BMP image", 95),
    ((b"fLaC",), "audio/flac", "FLAC audio", 100),
    ((b"OggS",), "audio/ogg", "Ogg container", 95),
)

_RIFF_TYPES = {
    b"WAVE": ("audio/wav", "WAVE audio"),
    b"AVI ": ("video/x-msvideo", "AVI video"),
    b"WEBP": ("image/webp", "WebP image"),
}

_OFFICE_MIMES = {
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


def signature_type(path, head):
    """Return a strong built-in type when the sample starts with a signature."""
    for prefixes, mime_type, description, confidence in _FIXED_SIGNATURES:
        if head.startswith(prefixes):
            return DetectedType(
                mime_type, description, "content_signature", confidence
            )
    riff = _riff_type(head)
    if riff is not None:
        return riff
    if len(head) >= 12 and head[4:8] == b"ftyp":
        return DetectedType(
            "video/mp4", "ISO Base Media file", "content_signature", 90
        )
    if head.startswith(b"PK\x03\x04"):
        return _zip_type(path)
    return None


def _riff_type(head):
    if not head.startswith(b"RIFF") or len(head) < 12:
        return None
    identified = _RIFF_TYPES.get(head[8:12])
    if identified is None:
        return None
    mime_type, description = identified
    return DetectedType(mime_type, description, "content_signature", 100)


def _zip_type(path):
    suffix = path.suffix.casefold().lstrip(".")
    identified = _OFFICE_MIMES.get(suffix)
    if identified is None:
        return DetectedType(
            "application/zip", "ZIP archive", "content_signature", 100
        )
    mime_type, description = identified
    return DetectedType(
        mime_type,
        description + " (ZIP container; subtype not verified)",
        "zip_container_plus_extension_hint",
        55,
    )
