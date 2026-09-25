"""Native PNG/GIF/BMP/JPEG header parsing for inspectImage."""

from __future__ import annotations

import os
import struct


_SOF_MARKERS = {
    0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
    0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF,
}
_SIZELESS_MARKERS = {
    0xD0, 0xD1, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7, 0xD8,
}


def _png(head):
    width, height = struct.unpack(">II", head[16:24])
    return {
        "width": width,
        "height": height,
        "format": "PNG",
        "depth": int(head[24]),
    }


def _gif(head):
    width, height = struct.unpack("<HH", head[6:10])
    return {"width": width, "height": height, "format": "GIF", "depth": 8}


def _bmp(head):
    width, height = struct.unpack("<ii", head[18:26])
    depth = struct.unpack("<H", head[28:30])[0]
    return {
        "width": width,
        "height": abs(height),
        "format": "BMP",
        "depth": depth,
    }


def _next_jpeg_marker(handle):
    marker = handle.read(2)
    if len(marker) < 2:
        return None
    if marker[0] == 0xFF:
        return marker[1]
    while marker and marker[0] != 0xFF:
        marker = handle.read(1)
    if not marker:
        return None
    suffix = handle.read(1)
    return suffix[0] if suffix else None


def _jpeg_sof(handle):
    precision = handle.read(1)
    height_bytes = handle.read(2)
    width_bytes = handle.read(2)
    components_bytes = handle.read(1)
    if (
        len(precision) < 1
        or len(height_bytes) < 2
        or len(width_bytes) < 2
        or len(components_bytes) < 1
    ):
        return None
    height = struct.unpack(">H", height_bytes)[0]
    width = struct.unpack(">H", width_bytes)[0]
    components = int(components_bytes[0])
    return {
        "width": width,
        "height": height,
        "format": "JPEG",
        "depth": int(precision[0]) * components,
    }


def parse_jpeg(handle):
    """Scan JPEG markers until a Start Of Frame segment is found."""
    try:
        if handle.read(2) != b"\xff\xd8":
            return None
        while True:
            marker_type = _next_jpeg_marker(handle)
            if marker_type is None or marker_type == 0xD9:
                return None
            if marker_type in _SIZELESS_MARKERS:
                continue
            length_bytes = handle.read(2)
            if len(length_bytes) < 2:
                return None
            length = struct.unpack(">H", length_bytes)[0]
            if marker_type in _SOF_MARKERS:
                return _jpeg_sof(handle)
            if length < 2:
                return None
            handle.seek(length - 2, os.SEEK_CUR)
    except Exception:
        return None


def parse_image(filepath):
    """Dispatch binary parsing from the file signature."""
    try:
        with open(filepath, "rb") as handle:
            head = handle.read(32)
            if len(head) < 10:
                return None
            if head.startswith(b"\x89PNG\r\n\x1a\n"):
                return _png(head)
            if head.startswith((b"GIF87a", b"GIF89a")):
                return _gif(head)
            if head.startswith(b"BM"):
                return _bmp(head)
            if head.startswith(b"\xff\xd8"):
                handle.seek(0)
                return parse_jpeg(handle)
    except Exception:
        return None
    return None
